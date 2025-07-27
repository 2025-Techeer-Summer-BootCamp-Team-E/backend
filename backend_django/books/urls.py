from django.urls import path
from .views import BookTextUploadView, BookFromPdfView, BookOfficialView, BookVideosView, BookFromPdfAsyncView  # BookStatusView는 더 이상 사용 안함
# BookCharactersView는 CharacterConditionalCreateOrListView로 대체됨
# characters 앱의 view들을 import (RESTful URL 구조를 위해)
from characters.views import (
    CharacterConditionalCreateOrListView,
    CharacterGenerateAsyncView
    # CharacterTaskStatusView  # 더 이상 사용 안함 (polling 방식)
)
# EventStream views import
from .eventstream_views import (
    book_processing_eventstream,
    character_generation_eventstream,
    script_generation_eventstream
)

urlpatterns = [
    path('text', BookTextUploadView.as_view()), # 책 텍스트 업로드 API

    path('pdf', BookFromPdfView.as_view()), # 책 PDF 업로드 API(동기)
    
    path('pdf/async', BookFromPdfAsyncView.as_view()), # 책 PDF 업로드 API (비동기)
    # path('<int:book_id>/status', BookStatusView.as_view()),  # 처리 상태 확인 API (Polling 방식 - 더 이상 사용 안함)

    path('official', BookOfficialView.as_view()), # 공용책 정보 API

    path('<int:book_id>/videos', BookVideosView.as_view()), # 책 동영상 API

    # === 캐릭터 관련 RESTful API ===
    path('<int:book_id>/characters', CharacterConditionalCreateOrListView.as_view()), # 캐릭터 조회/생성 (동기)
    path('<int:book_id>/characters/async', CharacterGenerateAsyncView.as_view()), # 캐릭터 생성 (비동기)
    # path('<int:book_id>/characters/tasks/<str:task_id>/status', CharacterTaskStatusView.as_view()), # 캐릭터 생성 상태 확인 (Polling 방식 - 더 이상 사용 안함)

    # === 실시간 알림 (EventStream) ===
    path('<int:book_id>/eventstream/processing', book_processing_eventstream), # 책 처리 상태
    path('<int:book_id>/eventstream/characters', character_generation_eventstream), # 캐릭터 생성 상태

    # path('<int:book_id>/characters', BookCharactersView.as_view()), # 기존 API (deprecated)

]
