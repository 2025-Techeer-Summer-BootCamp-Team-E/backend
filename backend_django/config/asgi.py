import os

import django

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path, re_path
import django_eventstream # django_eventstream 모듈 전체를 임포트


# 환경변수에 따라 설정 파일 선택
env = os.environ.get('DJANGO_ENV', 'dev')

if env == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')


django.setup()

from django.core.asgi import get_asgi_application

# Django-eventstream 5.2.0은 일반 Django URL 라우팅으로 충분함
# Django의 기본 ASGI 애플리케이션을 먼저 가져옵니다.
django_asgi_app = get_asgi_application()

# 이제 ProtocolTypeRouter를 사용하여 프로토콜에 따라 요청을 분기합니다.
application = ProtocolTypeRouter({
    # 일반적인 HTTP 요청은 Django의 기본 ASGI 앱이 처리합니다.
    "http": AuthMiddlewareStack( # AuthMiddlewareStack을 http 프로토콜 전체에 한 번만 적용
        URLRouter([
            # '/events/' 경로로 오는 SSE 요청은 django-eventstream이 처리합니다.
            # django_eventstream.urls.urlpatterns를 사용하여 URL 패턴을 포함합니다.
            path('events/', URLRouter(django_eventstream.urls.urlpatterns)),
            # 나머지 모든 HTTP 요청은 Django의 기본 ASGI 앱이 처리하도록 합니다.
            re_path(r'', django_asgi_app),
        ])
    ),
    # (나중에 웹소켓 등을 추가한다면 여기에 'websocket': AuthMiddlewareStack(URLRouter([...])) 을 추가할 수 있습니다.)
})

