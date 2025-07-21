from django.urls import path
# 기존 템플릿 기반 뷰들 (주석처리)
# from users.views import login_view, logout_view, signup, temp_view

# JWT API 뷰 import 추가
from users.views import LoginAPIView, SignupAPIView, UserInfoAPIView, CustomTokenRefreshView

urlpatterns = [
    # 기존 템플릿 기반 뷰들 (세션 인증) - 주석처리
    # path("login/", login_view),
    # path("logout/", logout_view),  # 로그아웃 뷰 추가
    # path("signup/", signup),  # 회원가입 뷰는 아직 구현되지 않았으므로 로그인 뷰로 임시 설정
    # path("temp/", temp_view),  # 임시 페이지 뷰 추가
    
    # JWT API 엔드포인트들
    path("login/", LoginAPIView.as_view()), # /users/login/
    path("signup/", SignupAPIView.as_view()),  # /users/signup/
    path("me/", UserInfoAPIView.as_view()), # /users/me
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"), # JWT 토큰 갱신 (Swagger 문서화 포함)
]
