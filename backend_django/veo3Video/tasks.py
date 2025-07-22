

from celery import shared_task
import os
import tempfile
import subprocess
from google.cloud import storage
import requests
from .veo_service import generate_signed_url, generate_video_from_text # generate_signed_url 함수 재사용
from .models import Video # Video 모델 임포트
from characters.models import Character
from narration.service.narration_service import generate_narration_for_character

# 환경 변수 설정 (veo_service.py에서 가져옴)
import os
from dotenv import load_dotenv
load_dotenv()
GOOGLE_CLOUD_GCS_BUCKET = os.getenv("GOOGLE_CLOUD_GCS_BUCKET")

@shared_task
def create_video_for_scene(character_id, prompt, title, lines):
    """
    Celery 작업으로 비디오 생성 및 나레이션 합성을 비동기적으로 처리합니다.
    """
    video_file_path = None
    audio_file_path = None
    combined_file_path = None
    try:
        # 1. 나레이션 생성
        transformed_lines = []
        for line_item in lines:
            if "line_ko" in line_item:
                transformed_lines.append({"speaker": line_item.get("speaker"), "text": line_item["line_ko"]})
            elif "line_en" in line_item:
                transformed_lines.append({"speaker": line_item.get("speaker"), "text": line_item["line_en"]})
            else:
                raise ValueError("Line item must contain 'line_ko' or 'line_en' field for narration.")

        narration_results = generate_narration_for_character(character_id=character_id, lines=transformed_lines)
        if not narration_results or not narration_results[0].get("audioUrl"):
            raise Exception("나레이션 생성에 실패했습니다.")
        narration_audio_url = narration_results[0]["audioUrl"]

        # 2. 비디오 생성 (기존 로직 재사용)
        video_generation_result = generate_video_from_text(prompt=prompt, title=title, character_id=character_id)
        if not video_generation_result or not video_generation_result.get("video_uri"):
            raise Exception("비디오 생성에 실패했습니다.")
        video_gcs_uri = video_generation_result["video_uri"]

        storage_client = storage.Client()
        bucket_name = GOOGLE_CLOUD_GCS_BUCKET.replace("gs://", "").rstrip('/')
        bucket = storage_client.bucket(bucket_name)

        # 3. GCS에서 비디오 다운로드
        video_blob_name = video_gcs_uri.replace(f"gs://{bucket_name}/", "")
        video_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        bucket.blob(video_blob_name).download_to_filename(video_file_path)
        print(f"Downloaded video {video_gcs_uri} to {video_file_path}")

        # 4. 나레이션 오디오 다운로드
        audio_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        audio_response = requests.get(narration_audio_url)
        audio_response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        with open(audio_file_path, 'wb') as f:
            f.write(audio_response.content)
        print(f"Downloaded audio {narration_audio_url} to {audio_file_path}")

        # 5. FFmpeg를 사용하여 비디오와 오디오 합성
        combined_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        ffmpeg_command = [
            "ffmpeg",
            "-i", video_file_path,
            "-i", audio_file_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "experimental",
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[a0]",
            "-map", "0:v:0",
            "-map", "[a0]",
            "-y", # Overwrite output files without asking
            combined_file_path
        ]
        print(f"Running ffmpeg command: {' '.join(ffmpeg_command)}")
        subprocess.run(ffmpeg_command, check=True, capture_output=True)
        print(f"Combined video and audio saved to {combined_file_path}")

        # 6. 합성된 비디오를 GCS에 업로드
        base_output_name = title.replace(' ', '_')
        extension = ".mp4"
        counter = 0
        output_blob_name = f"generated_videos/{base_output_name}{extension}"

        while bucket.blob(output_blob_name).exists():
            counter += 1
            output_blob_name = f"generated_videos/{base_output_name}_{counter}{extension}"
        
        output_blob = bucket.blob(output_blob_name)
        output_blob.upload_from_filename(combined_file_path)
        final_gcs_uri = f"gs://{bucket_name}/{output_blob_name}"
        print(f"Uploaded combined video with narration to {final_gcs_uri}")

        # 7. 데이터베이스 업데이트
        signed_url = generate_signed_url(final_gcs_uri)
        Video.objects.create(
            video_uri=final_gcs_uri,
            prompt=prompt,
            title=title,
            user_id=None, # user_id는 필요에 따라 설정
            character_id=character_id,
            narration_audio_url=narration_audio_url # 나레이션 URL 저장
        )
        print(f"Video with narration metadata saved to DB: {title}")
        print("영상생성이 완료되었습니다!")

        return {"status": "success", "gcs_uri": final_gcs_uri, "signed_url": signed_url}

    except Character.DoesNotExist:
        print(f"Error: Character with id {character_id} not found.")
        raise
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg command failed: {e}")
        print(f"Stdout: {e.stdout.decode()}")
        print(f"Stderr: {e.stderr.decode()}")
        raise
    except Exception as e:
        error_message = f"Error in create_video_for_scene for title '{title}': {e}"
        print(error_message)
        # 실패 시에도 명확한 상태를 반환하도록 수정
        return {"status": "failure", "reason": error_message, "title": title}
    finally:
        # 임시 파일 정리
        for f in [video_file_path, audio_file_path, combined_file_path]:
            if f and os.path.exists(f):
                os.remove(f)
                print(f"Cleaned up temporary file: {f}")

@shared_task(bind=True)
def combine_videos_task(self, results, output_title, user_id=None, character_id=None):
    """
    여러 GCS 비디오 URI를 받아 하나의 비디오로 합치고 GCS에 업로드합니다.
    이 태스크는 Celery chord의 콜백으로 사용됩니다.
    """
    video_uris = []
    failed_scenes = []
    for result in results:
        if result and result.get('status') == 'success':
            video_uris.append(result.get('gcs_uri'))
        else:
            failed_scenes.append(result.get('title', 'Unknown Scene'))

    if failed_scenes:
        error_reason = f"Failed to generate scenes: {', '.join(failed_scenes)}"
        self.update_state(state='FAILURE', meta={'reason': error_reason})
        raise Exception(error_reason)

    if not video_uris:
        self.update_state(state='FAILURE', meta={'reason': 'No successful scenes to combine.'})
        raise Exception("No successful scenes to combine.")

    storage_client = storage.Client()
    bucket_name = GOOGLE_CLOUD_GCS_BUCKET.replace("gs://", "").rstrip('/')
    bucket = storage_client.bucket(bucket_name)

    temp_files = []
    input_file_list_path = None
    combined_video_path = None

    try:
        # 1. GCS에서 각 비디오 다운로드
        for i, uri in enumerate(video_uris):
            blob_name = uri.replace(f"gs://{bucket_name}/", "")
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.mp4")
            temp_file.close()
            temp_files.append(temp_file.name)

            blob = bucket.blob(blob_name)
            blob.download_to_filename(temp_file.name)
            print(f"Downloaded {uri} to {temp_file.name}")

        # 2. FFmpeg를 사용하여 비디오 합치기
        # FFmpeg concat demuxer를 위한 파일 목록 생성
        input_file_list_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        for f in temp_files:
            input_file_list_path.write(f"file '{f}'\n".encode('utf-8'))
        input_file_list_path.close()
        print(f"Created ffmpeg input list: {input_file_list_path.name}")

        combined_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        combined_video_path.close()
        
        ffmpeg_command = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", input_file_list_path.name,
            "-c", "copy",
            "-y", # Overwrite output files without asking
            combined_video_path.name
        ]
        print(f"Running ffmpeg command: {' '.join(ffmpeg_command)}")
        subprocess.run(ffmpeg_command, check=True, capture_output=True)
        print(f"Combined video saved to {combined_video_path.name}")

        # 3. 합쳐진 비디오를 GCS에 업로드
        base_output_name = output_title.replace(' ', '_')
        extension = ".mp4"
        counter = 0
        output_blob_name = f"combined_videos/{base_output_name}{extension}"

        while bucket.blob(output_blob_name).exists():
            counter += 1
            output_blob_name = f"combined_videos/{base_output_name}_{counter}{extension}"
        
        output_blob = bucket.blob(output_blob_name)
        output_blob.upload_from_filename(combined_video_path.name)
        final_gcs_uri = f"gs://{bucket_name}/{output_blob_name}"
        print(f"Uploaded combined video to {final_gcs_uri}")

        # 4. 데이터베이스 업데이트 (선택 사항: 필요에 따라 Video 모델에 저장)
        signed_url = generate_signed_url(final_gcs_uri)
        print(f"Combined video signed URL: {signed_url}") # 추가된 라인
        Video.objects.create(
            video_uri=final_gcs_uri,
            prompt=f"Combined video: {', '.join(video_uris)}",
            title=output_title,
            user_id=user_id,
            character_id=character_id,
            # 기타 필요한 필드 추가
        )
        print(f"Combined video metadata saved to DB: {output_title}")

        return {"status": "success", "gcs_uri": final_gcs_uri, "signed_url": signed_url}

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg command failed: {e}")
        print(f"Stdout: {e.stdout.decode()}")
        print(f"Stderr: {e.stderr.decode()}")
        raise
    except Exception as e:
        print(f"Error combining videos: {e}")
        raise
    finally:
        # 5. 임시 파일 정리
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                print(f"Cleaned up temporary file: {f}")
        if input_file_list_path and os.path.exists(input_file_list_path.name):
            os.remove(input_file_list_path.name)
            print(f"Cleaned up temporary input list: {input_file_list_path.name}")
        if combined_video_path and os.path.exists(combined_video_path.name):
            os.remove(combined_video_path.name)
            print(f"Cleaned up temporary combined video: {combined_video_path.name}")
