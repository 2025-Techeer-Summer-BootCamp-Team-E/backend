"""
URL configuration for backend_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django_prometheus import exports
from config.views import index
from django.conf import settings
from django.urls import re_path
import django_eventstream
# from django_eventstream import get_event_stream_response


from django.urls import path, include, re_path # re_path도 필요
from config.asgi import application as asgi_app # asgi.py의 application을 임포트

urlpatterns = [
    path('admin/', admin.site.urls),
    path("metrics", exports.ExportToDjangoView),
    path('books/', include('books.urls')),  # Books 애플리케이션의 URL 포함
    # path('videos/', include('veo3Video.urls')),
    path('characters/', include('characters.urls')),
    path('users/', include('users.urls')),

    # path('events/', get_event_stream_response, name='eventstream'),

    

    # re_path(r'^events/', asgi_app), # /events/로 시작하는 모든 요청을 asgi_app으로 보냄

    path("", index),
    
    path('', include('django_prometheus.urls')),
]


'''DEBUG=TRUE, 개발환경일때만 Swagger UI를 사용'''
if settings.DEBUG:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    from rest_framework import permissions
    from django.conf.urls.static import static

    # Swagger 설정 (JWT 인증 포함)
    schema_view = get_schema_view(
        openapi.Info(
            title="EpiLog API",
            default_version='v1',
            description="""
EpiLog API 문서

## 인증 방법
JWT Bearer Token 인증을 사용합니다.

### 1단계: 토큰 발급
- `/users/login/` 또는 `/users/signup/` API로 JWT 토큰을 발급받으세요.

### 2단계: 인증 설정
- 🔒 **Authorize** 버튼을 클릭하세요.
- **Bearer** 섹션에 발급받은 access_token을 입력하세요.
- **Bearer** 단어는 자동으로 추가됩니다!

### 3단계: API 호출
- 이제 인증이 필요한 모든 API를 호출할 수 있습니다.

## 토큰 갱신
- Access Token이 만료되면 `/users/token/refresh/` API를 사용하여 갱신하세요.
            """,
            contact=openapi.Contact(email="epilog@example.com"),
            license=openapi.License(name="MIT License"),
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
        url='http://localhost:28000'
    )

    urlpatterns += [
        re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
        re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    ]

    # 개발환경에서 정적 파일 서빙
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
