from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField' # id가 자동증가하도록 설정
    name = 'users'
