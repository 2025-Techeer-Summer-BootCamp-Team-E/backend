from django.urls import path
from .views import CharacterConditionalCreateOrListView, ScriptGenerateView

urlpatterns = [
    path('books/<int:book_id>/', CharacterConditionalCreateOrListView.as_view()), # 캐릭터 생성 혹은 조회 기능
    path('<int:character_id>/script/', ScriptGenerateView.as_view()),  # 대본 생성 기능 

]
