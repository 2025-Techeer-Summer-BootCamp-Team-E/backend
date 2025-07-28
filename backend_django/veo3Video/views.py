from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import caches
from characters.models import Character # 이미 임포트되어 있음
from django.shortcuts import get_object_or_404
from .models import Video
from .serializers import VideoSerializer
from .veo_service import list_videos
from .tasks import create_video_for_scene, combine_videos_task
# veo3Vdideo/views.py : 컨트롤러.
# HTTP 상태 코드 반환에만 집중, 별도의 서비스 로직은 veo_servied.py에 분리. 또한 비동기 처리는 tasks.py에 일임

# 클라이언트로부터 받은 스크립트 데이터를 Redis 캐시에 저장
class ScriptCacheView(APIView):
    def post(self, request, *args, **kwargs):
        script_id = request.data.get("script_id")
        character_id = request.data.get("characterId")
        scenes = request.data.get("scenes")

        if not script_id or not character_id or not scenes:
            return Response({"error": "script_id, characterId, and scenes are required"}, status=status.HTTP_400_BAD_REQUEST)

        script_cache = caches['script_cache']
        # TTL을 10분으로 설정
        script_cache.set(f"script:{script_id}", {
            "characterId": character_id,
            "scenes": scenes
        }, timeout=600) 

        return Response({"message": "Script cached successfully.", "script_id": script_id}, status=status.HTTP_200_OK)

# 캐시된 스크립트 ID를 받아, 각 장면에 대한 비디오 생성
class VideoGenerationFromScriptView(APIView):
    def post(self, request, script_id, *args, **kwargs):
        script_cache = caches['script_cache']
        cached_data = script_cache.get(f"script:{script_id}")

        if not cached_data:
            return Response({"error": "Script not found in cache or expired"}, status=status.HTTP_404_NOT_FOUND)

        character_id = cached_data.get('characterId')
        scenes = cached_data.get('scenes', [])

        if not character_id or not scenes:
            return Response({"error": "Invalid script data in cache"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # character 객체를 여기서 가져옵니다.
            character_instance = Character.objects.get(id=character_id)
        except Character.DoesNotExist:
            return Response({"error": f"Character with id {character_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        for scene in scenes:
            prompt = scene.get('rewriting_prompt')
            scene_id = scene.get('sceneId')
            title = f"{character_instance.characterName} - Scene {scene_id}" # character_instance 사용
            # lines = scene.get('lines', []) # lines 데이터 추가

            if prompt:
                create_video_for_scene.delay(character_id=character_id, prompt=prompt, title=title)

        return Response({"message": f"Video generation started for {len(scenes)} scenes."}, status=status.HTTP_202_ACCEPTED)


# 텍스트-투-비디오 생성 API 뷰
# POST 요청을 처리하여 텍스트 프롬프트로부터 비디오 생성을 시작합니다。
class TextToVideoView(APIView):
    def post(self, request, *args, **kwargs):
        # 요청 본문에서 'prompt'와 'title' 필드를 추출합니다。
        prompt = request.data.get("prompt")
        title = request.data.get("title")
        character_id = request.data.get("character_id")
        # lines = request.data.get("lines", []) # lines 데이터 추가

        # [JWT 통합 예정] 여기에 JWT 방식으로 사용자 ID를 받아오는 기능 개발
        # 현재는 user_id를 None으로 설정하여 익명 사용자로 처리합니다。
        # 실제 구현 시에는 request.user.id 또는 JWT 토큰에서 사용자 ID를 추출하여 사용합니다。
        user_id = None

        # 필수 필드(prompt, title)가 누락되었는지 확인합니다。
        if not prompt or not title:
            # 필수 필드가 누락된 경우 400 Bad Request 응답을 반환합니다。
            return Response({"error": "Prompt and title are required"}, status=status.HTTP_400_BAD_REQUEST)

        create_video_for_scene.delay(character_id=character_id, prompt=prompt, title=title)

        return Response({"message": "Video generation started."}, status=status.HTTP_202_ACCEPTED)


# 비디오 목록 조회 및 전체 스토리 생성 API 뷰
# GET 요청: 데이터베이스에 저장된 비디오 목록을 반환합니다.
# POST 요청: 전체 스토리 비디오 생성을 시작합니다.
class VideoListView(APIView):
    def get(self, request, *args, **kwargs):
        # JWT 방식으로 사용자 ID를 가져옵니다.
        # request.user는 IsAuthenticated 권한 클래스에 의해 인증된 사용자 객체입니다.
        user_id = request.user.id if request.user.is_authenticated else None

        try:
            # user_id와 is_combined=True 필터를 사용하여 병합된 비디오 목록을 조회합니다.
            videos = list_videos(user_id=user_id, is_combined=True)
            return Response(videos, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        script_id = request.data.get("script_id")
        if not script_id:
            return Response({"error": "script_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # SSE 채널 ID 생성
        channel_id = f"video-generation-{uuid.uuid4()}"

        script_cache = caches['script_cache']
        cached_data = script_cache.get(f"script:{script_id}")

        if not cached_data:
            return Response({"error": "Script not found in cache or expired"}, status=status.HTTP_404_NOT_FOUND)

        character_id = cached_data.get('characterId')
        scenes = cached_data.get('scenes', [])
        user_id = None

        if not character_id or not scenes:
            return Response({"error": "Invalid script data in cache"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            character_instance = Character.objects.get(id=character_id)
        except Character.DoesNotExist:
            return Response({"error": f"Character with id {character_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        scene_tasks = []
        for scene in scenes:
            prompt = scene.get('rewriting_prompt')
            scene_id = scene.get('sceneId')
            title = f"{character_instance.characterName} - Scene {scene_id}"
            if prompt:
                scene_tasks.append(
                    create_video_for_scene.s(character_id=character_id, prompt=prompt, title=title, channel_id=channel_id)
                )

        if not scene_tasks:
            return Response({"error": "No scenes with prompts found to generate videos."}, status=status.HTTP_400_BAD_REQUEST)

        final_output_title = f"{character_instance.characterName}_FullStory"

        from celery import chord
        
        callback = combine_videos_task.s(
            output_title=final_output_title,
            user_id=user_id,
            character_id=character_id,
            channel_id=channel_id
        )
        
        chord(scene_tasks)(callback)

        # 작업 시작 이벤트 전송
        send_event(channel_id, 'message', {'status': 'process_started', 'message': f'Full story generation started for {character_instance.characterName}.'})

        return Response({"channel_id": channel_id}, status=status.HTTP_202_ACCEPTED)


class VideoBookmarkToggleView(APIView):
    def patch(self, request, videoId):
        video = get_object_or_404(Video, pk=videoId)
        video.is_bookmarked = not video.is_bookmarked
        video.save()
        serializer = VideoSerializer(video)
        return Response(serializer.data, status=status.HTTP_200_OK)

class BookmarkedVideoListView(APIView):
    def get(self, request):
        # 저장(is_deleted=True)되고 북마크된(is_bookmarked=True) 비디오만 가져옴
        bookmarked_videos = Video.objects.filter(is_deleted=True, is_bookmarked=True)
        serializer = VideoSerializer(bookmarked_videos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VideoDeleteView(APIView):
    def patch(self, request, videoId):
        video = get_object_or_404(Video, pk=videoId)
        is_deleted_request = request.data.get("is_deleted")

        # 요청에서 is_deleted 값을 boolean으로 변환 (0 -> False, 1 -> True)
        if is_deleted_request == 0:
            is_deleted_bool = False
        elif is_deleted_request == 1:
            is_deleted_bool = True
        else:
            return Response({"error": "Invalid value for is_deleted. Use 0 for delete, 1 for save."}, status=status.HTTP_400_BAD_REQUEST)

        video.is_deleted = is_deleted_bool
        video.save()

        # 응답 데이터 구성
        response_data = {
            "video_id": video.id,
            "is_deleted": 1 if video.is_deleted else 0 # 모델의 boolean 값을 1 또는 0으로 변환
        }
        return Response(response_data, status=status.HTTP_200_OK)


class CombineVideosView(APIView):
    def post(self, request, *args, **kwargs):
        video_uris = request.data.get("video_uris")
        output_title = request.data.get("output_title")
        user_id = request.data.get("user_id") # Optional
        character_id = request.data.get("character_id") # Optional

        if not video_uris or not isinstance(video_uris, list) or not output_title:
            return Response({"error": "video_uris (list) and output_title are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Celery 태스크 호출
        combine_videos_task.delay(video_uris, output_title, user_id, character_id)

        return Response({"message": "Video combination started."}, status=status.HTTP_202_ACCEPTED)


# import uuid
# from django_eventstream import send_event

# class FullStoryGenerationView(APIView):
#     """
#     전체 스토리 비디오 생성 프로세스를 시작하는 API 뷰.
#     이 뷰는 사용자가 캐시한 스크립트(ScriptCacheView를 통해)를 기반으로
#     여러 비디오 생성 및 병합 작업을 Celery를 통해 비동기적으로 조율합니다.
#
#     **처리 흐름:**
#     1.  **스크립트 데이터 검증 및 로드:**
#         *   요청에서 `script_id`를 받아 Redis 캐시에서 해당 스크립트 데이터를 조회합니다.
#         *   캐시된 데이터의 유효성(characterId, scenes 존재 여부)을 검증합니다.
#         *   캐릭터 정보를 데이터베이스에서 가져옵니다.
#     2.  **개별 장면 비디오 생성 태스크 준비 (병렬 처리):**
#         *   캐시된 스크립트의 각 `scene` (장면)을 반복합니다.
#         *   각 `scene`에 대해 `create_video_for_scene` Celery 태스크를 생성하고, 이 태스크들을 `scene_tasks` 리스트에 추가합니다.
#         *   `create_video_for_scene` 태스크는 다음을 담당합니다:
#             *   해당 장면의 텍스트 프롬프트로부터 비디오 생성 (Veo API 사용).
#             *   생성된 비디오와 나레이션 오디오를 FFmpeg를 사용하여 합성.
#             *   합성된 비디오를 Google Cloud Storage (GCS)에 업로드.
#             *   생성된 비디오의 메타데이터를 데이터베이스에 저장.
#         *   이 `scene_tasks`들은 Celery `chord`의 '헤더' 부분으로, 병렬로 실행될 예정입니다.
#     3.  **최종 비디오 병합 태스크 준비 (콜백 처리):**
#         *   모든 개별 장면 비디오 생성 태스크(`scene_tasks`)가 성공적으로 완료된 후에 실행될 `combine_videos_task` Celery 태스크를 '콜백'으로 설정합니다.
#         *   `combine_videos_task`는 다음을 담당합니다:
#             *   `scene_tasks`에서 반환된 모든 개별 비디오의 GCS URI를 수집.
#             *   수집된 비디오들을 FFmpeg를 사용하여 하나의 최종 비디오로 병합.
#             *   병합된 최종 비디오를 GCS에 업로드.
#             *   최종 비디오의 메타데이터를 데이터베이스에 저장.
#     4.  **Celery `chord` 실행:**
#         *   `celery.chord(scene_tasks)(callback)`를 호출하여 전체 비동기 워크플로우를 시작합니다.
#         *   이것은 "모든 장면 비디오가 생성되면, 그 결과들을 가지고 최종 비디오를 합쳐라"는 의미의 강력한 패턴입니다.
#
#     **요청 (POST):**
#     *   `script_id` (string, 필수): `ScriptCacheView`를 통해 캐시된 스크립트의 고유 ID.
#
#     **응답:**
#     *   `202 Accepted`: 비디오 생성 프로세스가 성공적으로 시작되었음을 알립니다. 실제 비디오 생성은 백그라운드에서 비동기적으로 진행됩니다.
#     *   `400 Bad Request`: `script_id`가 누락된 경우.
#     *   `404 Not Found`: 캐시에서 `script_id`에 해당하는 스크립트를 찾을 수 없거나 만료된 경우.
#     *   `500 Internal Server Error`: 캐시된 스크립트 데이터가 유효하지 않거나, 캐릭터를 찾을 수 없는 등 서버 내부 오류 발생 시.
#     """
#     def post(self, request, *args, **kwargs):
#         script_id = request.data.get("script_id")
#         if not script_id:
#             return Response({"error": "script_id is required"}, status=status.HTTP_400_BAD_REQUEST)
#
#         # SSE 채널 ID 생성
#         channel_id = f"video-generation-{uuid.uuid4()}"
#
#         script_cache = caches['script_cache']
#         cached_data = script_cache.get(f"script:{script_id}")
#
#         if not cached_data:
#             return Response({"error": "Script not found in cache or expired"}, status=status.HTTP_404_NOT_FOUND)
#
#         character_id = cached_data.get('characterId')
#         scenes = cached_data.get('scenes', [])
#         user_id = None
#
#         if not character_id or not scenes:
#             return Response({"error": "Invalid script data in cache"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#         try:
#             character_instance = Character.objects.get(id=character_id)
#         except Character.DoesNotExist:
#             return Response({"error": f"Character with id {character_id} not found"}, status=status.HTTP_404_NOT_FOUND)
#
#         scene_tasks = []
#         for scene in scenes:
#             prompt = scene.get('rewriting_prompt')
#             scene_id = scene.get('sceneId')
#             title = f"{character_instance.characterName} - Scene {scene_id}"
#             if prompt:
#                 scene_tasks.append(
#                     create_video_for_scene.s(character_id=character_id, prompt=prompt, title=title, channel_id=channel_id)
#                 )
#
#         if not scene_tasks:
#             return Response({"error": "No scenes with prompts found to generate videos."}, status=status.HTTP_400_BAD_REQUEST)
#
#         final_output_title = f"{character_instance.characterName}_FullStory"
#
#         from celery import chord
#         
#         callback = combine_videos_task.s(
#             output_title=final_output_title,
#             user_id=user_id,
#             character_id=character_id,
#             channel_id=channel_id
#         )
#         
#         chord(scene_tasks)(callback)
#
#         # 작업 시작 이벤트 전송
#         send_event(channel_id, 'message', {'status': 'process_started', 'message': f'Full story generation started for {character_instance.characterName}.'})
#
#         return Response({"channel_id": channel_id}, status=status.HTTP_202_ACCEPTED)