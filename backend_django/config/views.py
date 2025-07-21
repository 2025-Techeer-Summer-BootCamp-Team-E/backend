# config/views.py


from django.http import JsonResponse
from django.shortcuts import redirect

def index(request):
    """
    API 서버 상태 확인 엔드포인트
    JWT 환경에서는 세션 기반 리다이렉트 대신 API 상태를 반환
    """
    return JsonResponse({
        "status": "running",
        "message": "EpiLog API Server",
        "version": "v1.0",
        "auth_method": "JWT",
        "endpoints": {
            "auth": {
                "signup": "/users/signup/",
                "login": "/users/login/",
                "refresh": "/users/token/refresh/",
                "me": "/users/me/"
            },
            "docs": {
                "swagger": "/swagger/",
                "redoc": "/redoc/"
            }
        }
    })

# 기존 세션 기반 리다이렉트 (주석처리)
# def index(request):
#     # 사용자가 이미 로그인한 경우, 임시 페이지로 리다이렉트
#     if request.user.is_authenticated:
#         return redirect("/users/temp/")
#     # 사용자가 인증되지 않은 경우, 로그인 페이지로 리다이렉트
#     else:
#         return redirect("/users/login/")

