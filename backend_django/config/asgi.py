"""
ASGI config for backend_django project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# 환경변수에 따라 설정 파일 선택
env = os.environ.get('DJANGO_ENV', 'dev')  # 기본값은 dev

if env == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')

application = get_asgi_application()
