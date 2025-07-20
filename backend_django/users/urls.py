from django.urls import path
from users.views import login_view, logout_view, signup, temp_view

urlpatterns = [
    path("login/", login_view),
    path("logout/", logout_view),  # 로그아웃 뷰 추가
    path("signup/", signup),  # 회원가입 뷰는 아직 구현되지 않았으므로 로그인 뷰로 임시 설정
    path("temp/", temp_view),  # 임시 페이지 뷰 추가
]