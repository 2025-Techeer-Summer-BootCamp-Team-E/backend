from django.urls import path
from .views import (
    # CharacterConditionalCreateOrListView,  # books 앱으로 이동
    ScriptGenerateView,
    ScriptGenerateAsyncView,
    ScriptTaskStatusView,
    # CharacterGenerateAsyncView,  # books 앱으로 이동
    # CharacterTaskStatusView      # books 앱으로 이동
)

urlpatterns = [
    # === 캐릭터 생성 관련 URL들 → books 앱으로 이동됨 ===
    # path('books/<int:book_id>', CharacterConditionalCreateOrListView.as_view()), # → books/<int:book_id>/characters
    # path('books/<int:book_id>/async', CharacterGenerateAsyncView.as_view()),     # → books/<int:book_id>/characters/async
    # path('character-tasks/<str:task_id>/status', CharacterTaskStatusView.as_view()), # → books/<int:book_id>/characters/tasks/<task_id>/status
    
    # === 대본 생성 관련 URL들 (characters 앱에 유지) ===
    path('<int:character_id>/scripts', ScriptGenerateView.as_view()),  # 대본 생성 기능 (동기)
    path('<int:character_id>/scripts/async', ScriptGenerateAsyncView.as_view()),  # 대본 생성 기능 (비동기)
    path('tasks/<str:task_id>/status', ScriptTaskStatusView.as_view()),  # 대본 생성 상태 확인 (Redis 기반)

]
