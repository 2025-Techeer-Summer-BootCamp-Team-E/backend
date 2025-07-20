'''
미들웨어 설정을 위한 파일

1. 인증 기능 관련 필터를 정의
'''
from django.conf import settings
from django.shortcuts import redirect

'''로그인 인증 미들웨어
사용자가 인증되지 않은 경우, 로그인 페이지로 리다이렉트합니다.
혹은 인증이 필요없는 경로는 필터에서 제외합니다.
Ex. swagger, metrics 등
'''
class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # 필터를 통과할 경로 정의
        self.exempt_urls = getattr(settings, 'SWAGGER_EXEMPT_URLS', []) # SWAGGER_EXEMPT_URLS : Swagger 관련 경로

    def __call__(self, request):
    # 인증 미들웨어가 실행되기 전이면 request.user가 없음
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            if not any(request.path.startswith(url) for url in self.exempt_urls):
                return redirect(settings.LOGIN_URL)
        return self.get_response(request)