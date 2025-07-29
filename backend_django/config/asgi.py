import os

import django

from django.core.asgi import get_asgi_application


# 환경변수에 따라 설정 파일 선택
env = os.environ.get('DJANGO_ENV', 'dev')

if env == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')


application = get_asgi_application()

