from django.urls import path
from .views import VideoListView, VideoBookmarkToggleView, BookmarkedVideoListView, ScriptCacheView, VideoDeleteView

# veo3Video 앱의 URL 패턴을 정의합니다.
# 이 파일은 config/urls.py에서 include되어 사용됩니다.
urlpatterns = [
    # TextToVideoView는 POST 요청을 처리, 텍스트로부터 비디오 생성 요청.
    # # 'generate/' 경로에 대한 URL 패턴 정의, http://localhost:28000/voe3Video/ + generate/ 으로 api 요청
    # name='generate_video'는 이 URL 패턴의 이름을 지정, 템플릿이나 다른 코드에서 사용할 수 있도록 alias.
    # path('generate/', TextToVideoView.as_view(), name='generate_video'),

    # videos/ (POST): 캐시된 스크립트를 기반으로 전체 스토리 비디오 생성을 시작
    # videos/ (GET): 생성된 전체 스토리 비디오 목록을 조회
    path('', VideoListView.as_view(), name='list_videos'),

    # 영상 북마크
    path('bookmarks/videos/<int:videoId>', VideoBookmarkToggleView.as_view(), name = 'toggle_bookmark'),
    # 북마크된 영상 조회
    path('bookmarks/bookmarked', BookmarkedVideoListView.as_view(), name = 'list_bookmarked_videos'),

    # 영상 삭제 (Soft Delete)
    path('videos/<int:videoId>/', VideoDeleteView.as_view(), name='delete_video'),

    # path('generate/script/<str:script_id>/', VideoGenerationFromScriptView.as_view(), name='generate_video_from_script'),
    # path('combine/', CombineVideosView.as_view(), name='combine_videos'),
    # path('generate/full-story/', FullStoryGenerationView.as_view(), name='generate_full_story'),
    # 전체 스토리 생성을 위해 스크립트를 캐시에 저장
    path('cache-script/', ScriptCacheView.as_view(), name='cache_script'),
]