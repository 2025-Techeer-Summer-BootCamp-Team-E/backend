# from celery import shared_task
# import os
# import subprocess
# from .veo_service import generate_signed_url, generate_video_from_text
# from .models import Video
# from characters.models import Character
# import redis
# import json
# from django.conf import settings

# # Redis 클라이언트 초기화
# # settings.py에서 REDIS_HOST와 REDIS_PORT를 가져와 사용합니다.
# # Redis 클라이언트 초기화
# # 환경 변수에서 REDIS_HOST와 REDIS_PORT를 가져와 사용합니다。
# REDIS_HOST = os.getenv("REDIS_HOST", "backend-redis")
# REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)
# from google.cloud import storage
# import tempfile
# from datetime import datetime
# import uuid

# # 환경 변수 설정 (veo_service.py에서 가져옴)
# from dotenv import load_dotenv
# load_dotenv()
# GOOGLE_CLOUD_GCS_BUCKET = os.getenv("GOOGLE_CLOUD_GCS_BUCKET")

# @shared_task
# def create_video_for_scene(character_id, prompt, title, channel_id, user_id=None):
#     """
#     Celery 작업으로 비디오 생성을 비동기적으로 처리하고 SSE로 진행 상황을 알립니다.
#     """
#     try:
#         redis_client.publish(channel_id, json.dumps({'status': 'scene_creation_started', 'title': title}))

#         video_generation_result = generate_video_from_text(
#             prompt=prompt,
#             title=title,
#             character_id=character_id
#         )
#         if not video_generation_result or not video_generation_result.get("video_uri"):
#             raise Exception("비디오 생성에 실패했습니다.")
        
#         final_gcs_uri = video_generation_result["video_uri"]
#         print(f"Video generated and saved to GCS: {final_gcs_uri}")
#         signed_url = generate_signed_url(final_gcs_uri)

#         # 2. 데이터베이스 업데이트
#         # 비디오 생성 결과를 직접 DB에 저장 (is_combined=False)
#         # combine_videos_task에서 최종 병합 후 is_combined=True로 별도 저장
#         Video.objects.create(
#             video_uri=final_gcs_uri,
#             prompt=prompt,
#             title=title,
#             user_id=user_id, # user_id는 필요에 따라 설정
#             character_id=character_id,
#             is_combined=False # 개별 장면 영상으로 표시
#         )
#         print(f"Video metadata saved to DB: {title}")
#         print("영상생성이 완료되었습니다!")

#         redis_client.publish(channel_id, json.dumps({
#             'status': 'scene_creation_success',
#             'title': title,
#             'gcs_uri': final_gcs_uri
#         }))
#         # combine_videos_task로 전달할 결과 반환
#         return {
#             "status": "success",
#             "gcs_uri": final_gcs_uri,
#             "signed_url": signed_url,
#             "title": title
#         }

#     except Character.DoesNotExist:
#         # 실패 시에도 명확한 상태를 반환하도록 수정
#         print(f"Error: Character with id {character_id} not found.")
#         redis_client.publish(channel_id, json.dumps({
#             'status': 'scene_creation_failed',
#             'title': title,
#             'error': error_reason,
#         }))
#         return {"status": "failure", "reason": f"Character with id {character_id} not found.", "title": title}
#     except Exception as e:
#         error_message = f"Error in create_video_for_scene for title '{title}': {e}"
#         redis_client.publish(channel_id, json.dumps({
#             'status': 'scene_creation_failed',
#             'title': title,
#             'error': str(e),
#         }))
#         return {"status": "failure", "reason": str(e), "title": title}

# @shared_task(bind=True)
# def combine_videos_task(self, results, output_title, user_id=None, character_id=None, channel_id=None):
#     """
#     여러 GCS 비디오 URI를 받아 하나의 비디오로 합치고 GCS에 업로드하며 SSE로 진행 상황을 알립니다.
#     """
#     if not channel_id:
#         print("Error: channel_id not provided to combine_videos_task")
#         # Or handle this error appropriately
#         return

#     video_uris = []
#     failed_scenes = []
#     for result in results:
#         if result and result.get('status') == 'success':
#             video_uris.append(result.get('gcs_uri'))
#         else:
#             failed_scenes.append(result.get('title', 'Unknown Scene'))

#     if failed_scenes:
#         error_reason = f"Failed to generate scenes: {', '.join(failed_scenes)}"
#         redis_client.publish(channel_id, json.dumps({'status': 'error', 'message': error_reason}))
#         redis_client.publish(channel_id, json.dumps({'status': 'failed', 'message': 'Combination failed, closing connection'}))
#         self.update_state(state='FAILURE', meta={'reason': error_reason})
#         raise Exception(error_reason)

#     redis_client.publish(channel_id, json.dumps({
#         'status': 'combination_started',
#         'message': 'All scenes generated. Starting combination.'
#     }))


#     storage_client = storage.Client()
#     bucket_name = GOOGLE_CLOUD_GCS_BUCKET.replace("gs://", "").rstrip('/')
#     bucket = storage_client.bucket(bucket_name)

#     temp_files = []
#    # input_file_list_path = None
#    # combined_video_path = None

#     try:
#         # 1. GCS에서 각 비디오 다운로드
#         for i, uri in enumerate(video_uris):
#             blob_name = uri.replace(f"gs://{bucket_name}/", "")
#             temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.mp4")
#             temp_file.close()
#             temp_files.append(temp_file.name)
#             blob = bucket.blob(blob_name)
#             blob.download_to_filename(temp_file.name)
#             print(f"Downloaded {uri} to {temp_file.name}")

#         redis_client.publish(channel_id, json.dumps({
#                    'status': 'combination_progress',
#                     'message': 'Downloaded all videos. Combining with FFmpeg.'
#                     }))

#         # 2. FFmpeg를 사용하여 비디오 합치기
#         # FFmpeg concat demuxer를 위한 파일 목록 생성
#         input_file_list_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
#         for f in temp_files:
#             input_file_list_file.write(f"file '{f}'\n".encode('utf-8'))
#         input_file_list_file.close()
#         print(f"Created ffmpeg input list: {input_file_list_file.name}")

#         combined_video_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
#         combined_video_file.close()
        
#         ffmpeg_command = [
#             "ffmpeg",
#             "-f", "concat",
#             "-safe", "0",
#             "-i", input_file_list_file.name,
#             "-c", "copy",
#             "-y", # Overwrite output files without asking
#             combined_video_file.name
#         ]
#         print(f"Running ffmpeg command: {' '.join(ffmpeg_command)}")
#         subprocess.run(ffmpeg_command, check=True, capture_output=True)
#         print(f"Combined video saved to {combined_video_file.name}")

#         redis_client.publish(channel_id, json.dumps({
#                    'status': 'combination_progress',
#                     'message': 'Combination complete. Uploading to GCS.'
#                     }))

#         # 3. 합쳐진 비디오를 GCS에 업로드
#         base_output_name = output_title.replace(' ', '_')
#         timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
#         unique_id = uuid.uuid4().hex[:8]
#         if character_id:
#             output_blob_name = f"combined_videos/{character_id}_{base_output_name}_{timestamp}_{unique_id}.mp4"
#         else:
#             output_blob_name = f"combined_videos/{base_output_name}_{timestamp}_{unique_id}.mp4"

#         while bucket.blob(output_blob_name).exists():
#             unique_id = uuid.uuid4().hex[:8]
#             if character_id:
#                 output_blob_name = f"combined_videos/{character_id}_{base_output_name}_{timestamp}_{unique_id}.mp4"
#             else:
#                 output_blob_name = f"combined_videos/{base_output_name}_{timestamp}_{unique_id}.mp4"
        
#         output_blob = bucket.blob(output_blob_name)
#         output_blob.upload_from_filename(combined_video_file.name)
#         final_gcs_uri = f"gs://{bucket_name}/{output_blob_name}"
#         print(f"Uploaded combined video to {final_gcs_uri}")

#         # 썸네일 추출 및 업로드
#         thumbnail_path = None
#         thumbnail_gcs_uri = None
#         try:
#             try:
#                 thumbnail_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
#                 # FFmpeg를 사용하여 비디오에서 썸네일 추출 (예: 1초 지점)
#                 ffmpeg_thumbnail_command = [
#                     "ffmpeg",
#                     "-y", # 기존 파일이 있으면 덮어쓰기
#                     "-i", combined_video_file.name,
#                     "-ss", "00:00:01", # 1초 지점
#                     "-vframes", "1",
#                     "-vf", "scale=320:-1", # 너비 320px로 스케일링, 높이는 비율 유지
#                     thumbnail_path
#                 ]
#                 # subprocess.run을 사용하여 stdout/stderr를 캡처하고 CalledProcessError를 처리
#                 result = subprocess.run(ffmpeg_thumbnail_command, check=True, capture_output=True, text=True)
#                 print(f"Thumbnail extracted to {thumbnail_path}")
#                 if result.stdout:
#                     print(f"FFmpeg stdout: {result.stdout}")
#                 if result.stderr:
#                     print(f"FFmpeg stderr: {result.stderr}")

#             except subprocess.CalledProcessError as e:
#                 error_detail = f"""FFmpeg command failed: {e.cmd}
# Stdout: {e.stdout}
# Stderr: {e.stderr}"""
#                 print(f"Error generating or uploading thumbnail: {error_detail}")
#                 thumbnail_gcs_uri = None
#             except Exception as thumb_e:
#                 print(f"Error generating or uploading thumbnail: {thumb_e}")
#                 thumbnail_gcs_uri = None

#             # 썸네일을 GCS에 업로드
#             thumbnail_blob_name = f"thumbnails/{base_output_name}_{timestamp}_{unique_id}.jpg"
#             # 썸네일 이름 중복 방지 루프 추가
#             while bucket.blob(thumbnail_blob_name).exists():
#                 unique_id = uuid.uuid4().hex[:8] # 새로운 unique_id 생성
#                 thumbnail_blob_name = f"thumbnails/{base_output_name}_{timestamp}_{unique_id}.jpg"

#             thumbnail_blob = bucket.blob(thumbnail_blob_name)
#             thumbnail_blob.upload_from_filename(thumbnail_path)
#             thumbnail_gcs_uri = f"gs://{bucket_name}/{thumbnail_blob_name}"
#             print(f"Uploaded thumbnail to {thumbnail_gcs_uri}")

#         except Exception as thumb_e:
#             print(f"Error generating or uploading thumbnail: {thumb_e}")
#             thumbnail_gcs_uri = None # 썸네일 생성 실패 시 None으로 설정

#         # 4. 데이터베이스 업데이트 (선택 사항: 필요에 따라 Video 모델에 저장)
#         signed_url = generate_signed_url(final_gcs_uri)
#         thumbnail_public_url = generate_signed_url(thumbnail_gcs_uri) if thumbnail_gcs_uri else None
#         print(f"Combined video signed URL: {signed_url}") # 추가된 라인
#         video_instance = Video.objects.create(
#             video_uri=final_gcs_uri,
#             prompt=f"Combined video: {', '.join(video_uris)}",
#             title=output_title,
#             user_id=user_id,
#             character_id=character_id,
#             is_combined=True, # 병합된 영상임을 표시
#             thumbnail_url=thumbnail_public_url, # 썸네일 공개 URL 추가
#             # 기타 필요한 필드 추가
#         )
#         print(f"Combined video metadata saved to DB: {output_title}")

#         character_instance = Character.objects.get(id=character_id)

#         redis_client.publish(channel_id, json.dumps({
#             'status': 'process_completed',
#             'message': '영상생성이 완료되었습니다!',
#             'video_url': signed_url,
#             'thumbnail_url': thumbnail_public_url,
#             'video_title': video_instance.title,
#             'character_name': character_instance.characterName
#         }))
#         redis_client.publish(channel_id, json.dumps({'status': 'success', 'message': 'Combination completed successfully, closing connection'}))

#         return {"status": "success", "gcs_uri": final_gcs_uri, "signed_url": signed_url}

#     except Exception as e:
#         error_message = f"Error combining videos: {e}"
#         print(error_message)
#         redis_client.publish(channel_id, json.dumps({'status': 'error', 'message': error_message}))
#         redis_client.publish(channel_id, json.dumps({'status': 'failed', 'message': 'Task failed, closing connection'}))
#         raise
#     finally:
#         # 5. 임시 파일 정리
#         for f in temp_files:
#             if os.path.exists(f):
#                 os.remove(f)
#                 print(f"Cleaned up temporary file: {f}")
#         if input_file_list_file and os.path.exists(input_file_list_file.name):
#             os.remove(input_file_list_file.name)
#             print(f"Cleaned up temporary input list: {input_file_list_file.name}")
#         if combined_video_file and os.path.exists(combined_video_file.name):
#             os.remove(combined_video_file.name)
#             print(f"Cleaned up temporary combined video: {combined_video_file.name}")
#         if thumbnail_path and os.path.exists(thumbnail_path):
#             os.remove(thumbnail_path)
#             print(f"Cleaned up temporary thumbnail: {thumbnail_path}")
