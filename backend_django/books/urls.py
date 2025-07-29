from django.urls import path
from .views import BookFromPdfView, BookOfficialView, BookVideosView, BookFromPdfAsyncView  # BookStatusView는 더 이상 사용 안함
from . import views
# BookCharactersView는 CharacterConditionalCreateOrListView로 대체됨
# characters 앱의 view들을 import (RESTful URL 구조를 위해)
from characters.views import (
    CharacterConditionalCreateOrListView,
    CharacterGenerateAsyncView
    # CharacterTaskStatusView  # 더 이상 사용 안함 (polling 방식)
)
# EventStream views import
# from .eventstream_views import (
#     # book_processing_eventstream,          # 주석처리됨
#     # character_generation_eventstream,     # 주석처리됨  
#     # script_generation_eventstream,        # 주석처리됨
#     # task_status_eventstream, 
#     # push_event - 더 이상 사용하지 않음
# )
# Streaming 통합 views import
from .streaming_views import (
    # BookPdfUploadStreamView,
    # CharacterGenerateStreamView
    task_status_eventstream  # task_id 기반 실시간 알림(new!)
)

urlpatterns = [
    # path('text', BookTextUploadView.as_view()), # 책 텍스트 업로드 API

    path('pdf', BookFromPdfView.as_view()), # 책 PDF 업로드 API(동기)
    
    path('pdf/async', BookFromPdfAsyncView.as_view()), # 책 PDF 업로드 API (비동기)
    # path('<int:book_id>/status', BookStatusView.as_view()),  # 처리 상태 확인 API (Polling 방식 - 더 이상 사용 안함)

    # === 🚀 새로운 스트리밍 통합 API (POST + SSE) ===
    # path('pdf/stream', BookPdfUploadStreamView.as_view()), # 책 PDF 업로드 + 실시간 스트리밍

    path('official', BookOfficialView.as_view()), # 공용책 정보 API

    path('<int:book_id>/videos', BookVideosView.as_view()), # 책 동영상 API

    # === 캐릭터 관련 RESTful API ===
    path('<int:book_id>/characters', CharacterConditionalCreateOrListView.as_view()), # 캐릭터 조회/생성 (동기)
    path('<int:book_id>/characters/async', CharacterGenerateAsyncView.as_view()), # 캐릭터 생성 (비동기)
    # path('<int:book_id>/characters/tasks/<str:task_id>/status', CharacterTaskStatusView.as_view()), # 캐릭터 생성 상태 확인 (Polling 방식 - 더 이상 사용 안함)

    # === 🚀 새로운 스트리밍 통합 API (POST + SSE) ===
    # path('<int:book_id>/characters/stream', CharacterGenerateStreamView.as_view()), # 캐릭터 생성 + 실시간 스트리밍

    # === 실시간 알림 (EventStream) ===
    # path('<int:book_id>/eventstream/processing', book_processing_eventstream), # 책 처리 상태
    # path('<int:book_id>/eventstream/characters', character_generation_eventstream), # 캐릭터 생성 상태
    
    # === task_id 기반 실시간 알림 (권장) ===
    path('tasks/<str:task_id>/eventstream', task_status_eventstream), # 범용 작업 상태 (task_id 기반)

    # === 🧪 SSE 테스트용 엔드포인트 ===
    # path('test-sse/', views.test_sse_view, name='test-sse'),

    # path('<int:book_id>/characters', BookCharactersView.as_view()), # 기존 API (deprecated)

]
