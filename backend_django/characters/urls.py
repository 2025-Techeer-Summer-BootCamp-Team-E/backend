from django.urls import path
from .views import (
    # CharacterConditionalCreateOrListView,  # books 앱으로 이동
    ScriptGenerateView,
    ScriptGenerateAsyncView,
    # ScriptTaskStatusView,        # 더 이상 사용 안함 (polling 방식)
    # CharacterGenerateAsyncView,  # books 앱으로 이동
    # CharacterTaskStatusView      # books 앱으로 이동
)
# EventStream views import (books 앱에서 import)
# from books.eventstream_views import script_generation_eventstream  # 주석처리됨
# Streaming 통합 views import
# from books.streaming_views import ScriptGenerateStreamView

urlpatterns = [
    # === 캐릭터 생성 관련 URL들 → books 앱으로 이동됨 ===
    # path('books/<int:book_id>', CharacterConditionalCreateOrListView.as_view()), # → books/<int:book_id>/characters
    # path('books/<int:book_id>/async', CharacterGenerateAsyncView.as_view()),     # → books/<int:book_id>/characters/async
    # path('character-tasks/<str:task_id>/status', CharacterTaskStatusView.as_view()), # → books/<int:book_id>/characters/tasks/<task_id>/status
    
    # === 대본 생성 관련 URL들 (characters 앱에 유지) ===
    path('<int:character_id>/scripts', ScriptGenerateView.as_view()),  # 대본 생성 기능 (동기)
    path('<int:character_id>/scripts/async', ScriptGenerateAsyncView.as_view()),  # 대본 생성 기능 (비동기)
    # path('tasks/<str:task_id>/status', ScriptTaskStatusView.as_view()),  # 대본 생성 상태 확인 (Polling 방식 - 더 이상 사용 안함)

    # === 🚀 새로운 스트리밍 통합 API (POST + SSE) ===
    # path('<int:character_id>/scripts/generate-stream', ScriptGenerateStreamView.as_view()),  # 대본 생성 + 실시간 스트리밍

    # === 실시간 알림 (EventStream) ===
    # path('scripts/<str:script_id>/eventstream', script_generation_eventstream), # 대본 생성 상태 (script_id 기반) - 주석처리됨

]
