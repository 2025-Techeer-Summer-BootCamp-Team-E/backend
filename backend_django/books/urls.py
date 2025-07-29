from django.urls import path
from .views import BookFromPdfView, BookOfficialView, BookVideosView, BookFromPdfAsyncView  # BookStatusView는 더 이상 사용 안함
from . import views

from characters.views import (
    CharacterConditionalCreateOrListView,
    CharacterGenerateAsyncView

)
urlpatterns = [
    # path('text', BookTextUploadView.as_view()), # 책 텍스트 업로드 API

    path('pdf', BookFromPdfView.as_view()), # 책 PDF 업로드 API(동기)
    
    path('pdf/async', BookFromPdfAsyncView.as_view()), # 책 PDF 업로드 API (비동기)


    path('official', BookOfficialView.as_view()), # 공용책 정보 API

    path('<int:book_id>/videos', BookVideosView.as_view()), # 책 동영상 API

    # === 캐릭터 관련 RESTful API => 기존에 Characters 폴더에 있었지만, RESTful 설계를 위해 옮겼습니다.===
    path('<int:book_id>/characters', CharacterConditionalCreateOrListView.as_view()), # 캐릭터 조회/생성 (동기)
    path('<int:book_id>/characters/async', CharacterGenerateAsyncView.as_view()), # 캐릭터 생성 (비동기)    
    # === task_id 기반 실시간 알림 (직접 SSE 구현) ===
    path('tasks/<str:task_id>/eventstream', views.task_eventstream_view), # 범용 작업 상태 (task_id 기반)

]
