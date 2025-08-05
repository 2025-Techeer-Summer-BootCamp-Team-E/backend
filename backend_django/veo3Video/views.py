# import os
# import uuid
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from django.core.cache import caches
# from characters.models import Character # 이미 임포트되어 있음
# from django.shortcuts import get_object_or_404
# from .models import Video
# from .serializers import VideoSerializer
# from .veo_service import list_videos
# from .tasks import create_video_for_scene, combine_videos_task
# from celery import chord
# from django.http import StreamingHttpResponse
# import redis
# import json
# from django.conf import settings

# # Redis 클라이언트 초기화
# REDIS_HOST = os.getenv("REDIS_HOST", "backend-redis")
# REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)
# import time
# from rest_framework.permissions import AllowAny
# # veo3Vdideo/views.py : 컨트롤러.
# # HTTP 상태 코드 반환에만 집중, 별도의 서비스 로직은 veo_servied.py에 분리. 또한 비동기 처리는 tasks.py에 일임

# # 클라이언트로부터 받은 스크립트 데이터를 Redis 캐시에 저장
# class ScriptCacheView(APIView):
#     def post(self, request, *args, **kwargs):
#         script_id = request.data.get("script_id")
#         character_id = request.data.get("characterId")
#         scenes = request.data.get("scenes")

#         if not script_id or not character_id or not scenes:
#             return Response({"error": "script_id, characterId, and scenes are required"}, status=status.HTTP_400_BAD_REQUEST)

#         script_cache = caches['script_cache']
#         # TTL을 10분으로 설정
#         script_cache.set(f"script:{script_id}", {
#             "characterId": character_id,
#             "scenes": scenes
#         }, timeout=600) 

#         return Response({"message": "Script cached successfully.", "script_id": script_id}, status=status.HTTP_200_OK)

# # 캐시된 스크립트 ID를 받아, 각 장면에 대한 비디오 생성
# class VideoGenerationFromScriptView(APIView):
#     def post(self, request, script_id, *args, **kwargs):
#         script_cache = caches['script_cache']
#         cached_data = script_cache.get(f"script:{script_id}")

#         if not cached_data:
#             return Response({"error": "Script not found in cache or expired"}, status=status.HTTP_404_NOT_FOUND)

#         character_id = cached_data.get('characterId')
#         scenes = cached_data.get('scenes', [])

#         if not character_id or not scenes:
#             return Response({"error": "Invalid script data in cache"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         try:
#             # character 객체를 여기서 가져옵니다.
#             character_instance = Character.objects.get(id=character_id)
#         except Character.DoesNotExist:
#             return Response({"error": f"Character with id {character_id} not found"}, status=status.HTTP_404_NOT_FOUND)

#         for scene in scenes:
#             prompt = scene.get('rewriting_prompt')
#             scene_id = scene.get('sceneId')
#             title = f"{character_instance.characterName} - Scene {scene_id}" # character_instance 사용
#             # lines = scene.get('lines', []) # lines 데이터 추가

#             if prompt:
#                 create_video_for_scene.delay(character_id=character_id, prompt=prompt, title=title)

#         return Response({"message": f"Video generation started for {len(scenes)} scenes."}, status=status.HTTP_202_ACCEPTED)


# # 텍스트-투-비디오 생성 API 뷰
# # POST 요청을 처리하여 텍스트 프롬프트로부터 비디오 생성을 시작합니다.
# class TextToVideoView(APIView):
#     def post(self, request, *args, **kwargs):
#         # 요청 본문에서 'prompt'와 'title' 필드를 추출합니다.
#         prompt = request.data.get("prompt")
#         title = request.data.get("title")
#         character_id = request.data.get("character_id")
#         # lines = request.data.get("lines", []) # lines 데이터 추가

#         # [JWT 통합 예정] 여기에 JWT 방식으로 사용자 ID를 받아오는 기능 개발
#         # 현재는 user_id를 None으로 설정하여 익명 사용자로 처리합니다.
#         # 실제 구현 시에는 request.user.id 또는 JWT 토큰에서 사용자 ID를 추출하여 사용합니다。
#         user_id = request.user.id if request.user.is_authenticated else None

#         # 필수 필드(prompt, title)가 누락되었는지 확인합니다.
#         if not prompt or not title:
#             # 필수 필드가 누락된 경우 400 Bad Request 응답을 반환합니다。
#             return Response({"error": "Prompt and title are required"}, status=status.HTTP_400_BAD_REQUEST)

#         create_video_for_scene.delay(character_id=character_id, prompt=prompt, title=title, user_id=user_id)

#         return Response({"message": "Video generation started."}, status=status.HTTP_202_ACCEPTED)


# # 비디오 목록 조회 및 전체 스토리 생성 API 뷰
# # GET 요청: 데이터베이스에 저장된 비디오 목록을 반환합니다.
# # POST 요청: 전체 스토리 비디오 생성을 시작합니다.
# class VideoListView(APIView):
#     def get(self, request, *args, **kwargs):
#         # JWT 방식으로 사용자 ID를 가져옵니다.
#         # request.user는 IsAuthenticated 권한 클래스에 의해 인증된 사용자 객체입니다.
#         user_id = request.user.id if request.user.is_authenticated else None

#         try:
#             # user_id와 is_combined=True 필터를 사용하여 병합된 비디오 목록을 조회합니다.
#             videos = Video.objects.filter(user_id=user_id, is_combined=True)
#             response_data = []

#             for v in videos:
#                 response_data.append({
#                     "video_id": v.id,
#                     "video_title": v.title,
#                     "character_id": v.character.id,
#                     "character_name": v.character.characterName,
#                     "character_description": v.character.characterDescription,
#                     "video_url": v.video_uri,
#                     "thumbnail_url": v.thumbnail_url,
#                     "is_bookmarked": v.is_bookmarked,
#                     "created_at": v.created_at.isoformat(), # ISO 8601 형식으로 변환
#                     "book_id": v.character.book.id if v.character and v.character.book else None,
#                     "book_name": v.character.book.title if v.character and v.character.book else None,
#                 })
#             return Response(response_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def post(self, request, *args, **kwargs):
#         script_id = request.data.get("script_id")
#         if not script_id:
#             return Response({"error": "script_id is required"}, status=status.HTTP_400_BAD_REQUEST)

#         # SSE 채널 ID 생성
#         channel_id = f"video-generation-{uuid.uuid4()}"

#         script_cache = caches['script_cache']
#         cached_data = script_cache.get(f"script:{script_id}")
#         user_id = request.user.id if request.user.is_authenticated else None

#         if not cached_data:
#             return Response({"error": "Script not found in cache or expired"}, status=status.HTTP_404_NOT_FOUND)

#         character_id = cached_data.get('characterId')
#         scenes = cached_data.get('scenes', [])

#         if not character_id or not scenes:
#             return Response({"error": "Invalid script data in cache"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         try:
#             character_instance = Character.objects.get(id=character_id)
#         except Character.DoesNotExist:
#             return Response({"error": f"Character with id {character_id} not found"}, status=status.HTTP_404_NOT_FOUND)

#         scene_tasks = []
#         for scene in scenes:
#             prompt = scene.get('rewriting_prompt')
#             scene_id = scene.get('sceneId')
#             title = f"{character_instance.characterName} - Scene {scene_id}"
#             if prompt:
#                 scene_tasks.append(
#                     create_video_for_scene.s(character_id=character_id, prompt=prompt, title=title, channel_id=channel_id, user_id=user_id)
#                 )

#         if not scene_tasks:
#             return Response({"error": "No scenes with prompts found to generate videos."}, status=status.HTTP_400_BAD_REQUEST)

#         final_output_title = f"{character_instance.characterName}_FullStory"


        
#         callback = combine_videos_task.s(
#             output_title=final_output_title,
#             user_id=user_id,
#             character_id=character_id,
#             channel_id=channel_id
#         )
        
#         chord(scene_tasks)(callback)

#         # 작업 시작 이벤트 전송
#         redis_client.publish(channel_id, json.dumps({'status': 'process_started', 'message': f'Full story generation started for {character_instance.characterName}.'}))

#         return Response({"channel_id": channel_id}, status=status.HTTP_202_ACCEPTED)


# class VideoBookmarkToggleView(APIView):
#     def patch(self, request, videoId):
#         video = get_object_or_404(Video, pk=videoId)
#         video.is_bookmarked = not video.is_bookmarked
#         video.save()
#         serializer = VideoSerializer(video)
#         return Response(serializer.data, status=status.HTTP_200_OK)

# class BookmarkedVideoListView(APIView):
#     def get(self, request):
#         # 저장(is_deleted=True)되고 북마크된(is_bookmarked=True) 비디오만 가져옴
#         bookmarked_videos = Video.objects.filter(is_deleted=True, is_bookmarked=True)
#         serializer = VideoSerializer(bookmarked_videos, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


# class VideoDeleteView(APIView):
#     def patch(self, request, videoId):
#         video = get_object_or_404(Video, pk=videoId)
#         is_deleted_request = request.data.get("is_deleted")

#         # 요청에서 is_deleted 값을 boolean으로 변환 (0 -> False, 1 -> True)
#         if is_deleted_request == 0:
#             is_deleted_bool = False
#         elif is_deleted_request == 1:
#             is_deleted_bool = True
#         else:
#             return Response({"error": "Invalid value for is_deleted. Use 0 for delete, 1 for save."}, status=status.HTTP_400_BAD_REQUEST)

#         video.is_deleted = is_deleted_bool
#         video.save()

#         # 응답 데이터 구성
#         response_data = {
#             "video_id": video.id,
#             "is_deleted": 1 if video.is_deleted else 0 # 모델의 boolean 값을 1 또는 0으로 변환
#         }
#         return Response(response_data, status=status.HTTP_200_OK)


# class CombineVideosView(APIView):
#     def post(self, request, *args, **kwargs):
#         video_uris = request.data.get("video_uris")
#         output_title = request.data.get("output_title")
#         user_id = request.data.get("user_id") # Optional
#         character_id = request.data.get("character_id") # Optional

#         if not video_uris or not isinstance(video_uris, list) or not output_title:
#             return Response({"error": "video_uris (list) and output_title are required"}, status=status.HTTP_400_BAD_REQUEST)

#         # Celery 태스크 호출
#         combine_videos_task.delay(video_uris, output_title, user_id, character_id)

#         return Response({"message": "Video combination started."}, status=status.HTTP_202_ACCEPTED)


# class VideoEventStreamView(APIView):
#     permission_classes = [AllowAny] # 인증 없이 접근 가능하도록 설정

#     def get(self, request, channel_id, *args, **kwargs):
#         def event_stream():
#             pubsub = redis_client.pubsub()
#             pubsub.subscribe(channel_id)
#             # 클라이언트 연결 유지 및 Redis 메시지 대기
#             for message in pubsub.listen():
#                 if message['type'] == 'message':
#                     data = json.loads(message['data'].decode('utf-8'))
#                     # SSE 형식으로 데이터 전송
#                     yield f"data: {json.dumps(data)}\n\n"
#                     time.sleep(0.01) # 버퍼링 방지를 위한 짧은 지연
#                     # 'close' 상태 메시지를 받으면 연결 종료
#                     if data.get('status') == 'failed' or data.get('status') == 'success':
#                         break
        
#         response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
#         response['Cache-Control'] = 'no-cache'
#         return response
