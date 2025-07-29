from celery import shared_task
import os
import subprocess
from .veo_service import generate_signed_url, generate_video_from_text
from .models import Video
from characters.models import Character
from django_eventstream import send_event
from google.cloud import storage
import tempfile
from datetime import datetime
import uuid

# 환경 변수 설정 (veo_service.py에서 가져옴)
from dotenv import load_dotenv
load_dotenv()
GOOGLE_CLOUD_GCS_BUCKET = os.getenv("GOOGLE_CLOUD_GCS_BUCKET")

@shared_task
def create_video_for_scene(character_id, prompt, title, channel_id):
    """
    Celery 작업으로 비디오 생성을 비동기적으로 처리하고 SSE로 진행 상황을 알립니다.
    """
    try:
        send_event(channel_id, 'message', {'status': 'scene_creation_started', 'title': title})

        video_generation_result = generate_video_from_text(prompt=prompt, title=title, character_id=character_id)
        if not video_generation_result or not video_generation_result.get("video_uri"):
            raise Exception("비디오 생성에 실패했습니다.")
        
        final_gcs_uri = video_generation_result["video_uri"]
        print(f"Video generated and saved to GCS: {final_gcs_uri}")

        # 2. 데이터베이스 업데이트
        # 비디오 생성 결과를 직접 DB에 저장 (is_combined=False)
        # combine_videos_task에서 최종 병합 후 is_combined=True로 별도 저장
        signed_url = generate_signed_url(final_gcs_uri)
        Video.objects.create(
            video_uri=final_gcs_uri,
            prompt=prompt,
            title=title,
            user_id=None, # user_id는 필요에 따라 설정
            character_id=character_id,
            is_combined=False # 개별 장면 영상으로 표시
        )
        print(f"Video metadata saved to DB: {title}")
        print("영상생성이 완료되었습니다!")

        send_event(channel_id, 'message', {'status': 'scene_creation_success', 'title': title, 'gcs_uri': final_gcs_uri})
        # combine_videos_task로 전달할 결과 반환
        return {"status": "success", "gcs_uri": final_gcs_uri, "signed_url": signed_url, "title": title}

    except Character.DoesNotExist:
        print(f"Error: Character with id {character_id} not found.")
        # 실패 시에도 명확한 상태를 반환하도록 수정
        return {"status": "failure", "reason": f"Character with id {character_id} not found.", "title": title}
    except Exception as e:
        error_message = f"Error in create_video_for_scene for title '{title}': {e}"
        print(error_message)
        send_event(channel_id, 'message', {'status': 'scene_creation_failed', 'title': title, 'error': str(e)})
        # 실패 시에도 명확한 상태를 반환하도록 수정
        return {"status": "failure", "reason": error_message, "title": title}

@shared_task(bind=True)
def combine_videos_task(self, results, output_title, user_id=None, character_id=None, channel_id=None):
    """
    여러 GCS 비디오 URI를 받아 하나의 비디오로 합치고 GCS에 업로드하며 SSE로 진행 상황을 알립니다.
    """
    if not channel_id:
        print("Error: channel_id not provided to combine_videos_task")
        # Or handle this error appropriately
        return

    video_uris = []
    failed_scenes = []
    for result in results:
        if result and result.get('status') == 'success':
            video_uris.append(result.get('gcs_uri'))
        else:
            failed_scenes.append(result.get('title', 'Unknown Scene'))

    if failed_scenes:
        error_reason = f"Failed to generate scenes: {', '.join(failed_scenes)}"
        send_event(channel_id, 'message', {'status': 'error', 'message': error_reason})
        send_event(channel_id, 'close', {'status': 'failed'})
        self.update_state(state='FAILURE', meta={'reason': error_reason})
        raise Exception(error_reason)

    if not video_uris:
        error_reason = "No successful scenes to combine."
        send_event(channel_id, 'message', {'status': 'error', 'message': error_reason})
        send_event(channel_id, 'close', {'status': 'failed'})
        self.update_state(state='FAILURE', meta={'reason': error_reason})
        raise Exception(error_reason)

    send_event(channel_id, 'message', {'status': 'combination_started', 'message': 'All scenes generated. Starting combination.'})

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

        send_event(channel_id, 'message', {'status': 'combination_progress', 'message': 'Downloaded all videos. Combining with FFmpeg.'})

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

        send_event(channel_id, 'message', {'status': 'combination_progress', 'message': 'Combination complete. Uploading to GCS.'})

        # 3. 합쳐진 비디오를 GCS에 업로드
        base_output_name = output_title.replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        if character_id:
            output_blob_name = f"combined_videos/{character_id}_{base_output_name}_{timestamp}_{unique_id}.mp4"
        else:
            output_blob_name = f"combined_videos/{base_output_name}_{timestamp}_{unique_id}.mp4"

        while bucket.blob(output_blob_name).exists():
            unique_id = uuid.uuid4().hex[:8]
            if character_id:
                output_blob_name = f"combined_videos/{character_id}_{base_output_name}_{timestamp}_{unique_id}.mp4"
            else:
                output_blob_name = f"combined_videos/{base_output_name}_{timestamp}_{unique_id}.mp4"
        
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
            is_combined=True, # 병합된 영상임을 표시
            # 기타 필요한 필드 추가
        )
        print(f"Combined video metadata saved to DB: {output_title}")
        send_event(channel_id, 'message', {'status': 'process_completed', 'message': 'Successfully generated the full story video.', 'signed_url': signed_url})
        send_event(channel_id, 'close', {'status': 'success'})

        return {"status": "success", "gcs_uri": final_gcs_uri, "signed_url": signed_url}

    except Exception as e:
        error_message = f"Error combining videos: {e}"
        print(error_message)
        send_event(channel_id, 'message', {'status': 'error', 'message': error_message})
        send_event(channel_id, 'close', {'status': 'failed'})
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
