
import os
from celery import Celery
import django
import environ

# 환경변수에 따라 설정 파일과 .env 파일 선택
env = environ.Env()
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# 환경변수 DJANGO_ENV에 따라 적절한 .env 파일 로드
django_env = os.environ.get('DJANGO_ENV', 'dev')
if django_env == 'prod':
    environ.Env.read_env(env_file=os.path.join(BASE_DIR, '.env.prod'))
    settings_module = 'config.settings_prod'
else:
    environ.Env.read_env(env_file=os.path.join(BASE_DIR, '.env.dev'))
    settings_module = 'config.settings_dev'

# Django의 settings 모듈을 환경에 맞게 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

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
