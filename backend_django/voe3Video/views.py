from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# veo_service.py에서 비디오 생성 및 목록 조회 로직을 임포트합니다.
from .veo_service import generate_video_from_text, list_videos

from django.shortcuts import get_object_or_404
from .models import Video
from .serializers import VideoSerializer

# 텍스트-투-비디오 생성 API 뷰
# POST 요청을 처리하여 텍스트 프롬프트로부터 비디오 생성을 시작합니다.
class TextToVideoView(APIView):
    def post(self, request, *args, **kwargs):
        # 요청 본문에서 'prompt'와 'title' 필드를 추출합니다.
        prompt = request.data.get("prompt")
        title = request.data.get("title")

        # [JWT 통합 예정] 여기에 JWT 방식으로 사용자 ID를 받아오는 기능 개발
        # 현재는 user_id를 None으로 설정하여 익명 사용자로 처리합니다.
        # 실제 구현 시에는 request.user.id 또는 JWT 토큰에서 사용자 ID를 추출하여 사용합니다.
        user_id = None

        # 필수 필드(prompt, title)가 누락되었는지 확인합니다.
        if not prompt or not title:
            # 필수 필드가 누락된 경우 400 Bad Request 응답을 반환합니다.
            return Response({"error": "Prompt and title are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # veo_service.py의 generate_video_from_text 함수를 호출하여 비디오 생성을 시작합니다.
            # user_id는 현재 None으로 전달됩니다.
            result = generate_video_from_text(prompt, title, user_id=user_id)
            # 비디오 생성 요청이 성공하면 200 OK 응답과 함께 결과를 반환합니다.
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            # 비디오 생성 중 오류가 발생하면 500 Internal Server Error 응답을 반환합니다.
            # 오류 메시지는 클라이언트에게 전달됩니다.
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 비디오 목록 조회 API 뷰
# GET 요청을 처리하여 데이터베이스에 저장된 비디오 목록을 반환합니다.
class VideoListView(APIView):
    def get(self, request, *args, **kwargs):
        # [JWT 통합 예정] 여기에 JWT 방식으로 사용자 ID를 받아오는 기능 개발
        # 현재는 user_id를 None으로 설정하여 모든 비디오를 조회합니다.
        # 실제 구현 시에는 request.user.id 또는 JWT 토큰에서 사용자 ID를 추출하여 사용합니다.
        user_id = None

        try:
            # veo_service.py의 list_videos 함수를 호출하여 비디오 목록을 조회합니다.
            # user_id가 전달되면 해당 사용자의 비디오만 필터링됩니다.
            videos = list_videos(user_id=user_id)
            # 비디오 목록 조회가 성공하면 200 OK 응답과 함께 목록을 반환합니다.
            return Response(videos, status=status.HTTP_200_OK)
        except Exception as e:
            # 비디오 목록 조회 중 오류가 발생하면 500 Internal Server Error 응답을 반환합니다.
            # 오류 메시지는 클라이언트에게 전달됩니다.
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoBookmarkToggleView(APIView):
    def patch(self, request, videoId):
        video = get_object_or_404(Video, pk=videoId)
        video.is_bookmarked = not video.is_bookmarked
        video.save()
        serializer = VideoSerializer(video)
        return Response(serializer.data, status=status.HTTP_200_OK)

class BookmarkedVideoListView(APIView):
    def get(self, request):
        bookmarked_videos = Video.objects.filter(is_bookmarked=True)    # 북마크된 비디오만 가져옴
        serializer = VideoSerializer(bookmarked_videos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
