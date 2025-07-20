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

urlpatterns = [
    path('admin/', admin.site.urls),
    path("metrics", exports.ExportToDjangoView),

    path('books/', include('books.urls')),
    path('videos/', include('videos.urls')),
    path('videos2/', include('videos2.urls')),
    path('voe3Video/', include('voe3Video.urls')),
    path('characters/', include('characters.urls')),
    path('users/', include('users.urls')),
    path("", index),
    path('narration/', include('narration.urls')),
    path('', include('django_prometheus.urls')),
]

'''DEBUG=TRUE, 개발환경일때만 Swagger UI를 사용'''
if settings.DEBUG:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    from rest_framework import permissions
    from django.conf.urls.static import static

    # Swagger 설정
    schema_view = get_schema_view(
        openapi.Info(
            title="EpiLog API",
            default_version='v1',
            description="API documentation for your project",
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
        url='http://localhost:28000'
    )

    urlpatterns += [
        re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]
    
    # 개발환경에서 정적 파일 서빙
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
