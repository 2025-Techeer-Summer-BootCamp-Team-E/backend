
import os
from celery import Celery
import django
import environ

# .env.dev 파일 명시적 로드
env = environ.Env()
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
environ.Env.read_env(env_file=os.path.join(BASE_DIR, '.env.dev'))

# Django의 settings 모듈을 Celery의 기본 설정으로 사용하도록 설정합니다.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')

# Django 완전 초기화 (설정과 앱 모두)
django.setup()

app = Celery('config')

# 여기서 문자열을 사용하는 것은 워커가 자식 프로세스에서 설정을 직렬화할 필요가 없다는 것을 의미합니다.
# namespace='CELERY'는 모든 Celery 관련 설정 키가 'CELERY_'라는 접두사를 가져야 함을 의미합니다.
app.config_from_object('django.conf:settings', namespace='CELERY')

# app.conf.update(
#     CELERY_RESULT_BACKEND='redis://backend-redis:6379/0',
# )
# 등록된 모든 Django 앱 설정에서 tasks.py 파일을 로드합니다.
# 명시적으로 태스크가 있는 앱들을 지정
# app.autodiscover_tasks(['books', 'characters', 'veo3Video'])
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
