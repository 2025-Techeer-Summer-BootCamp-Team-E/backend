from django.db import models
from django.contrib.auth.models import AbstractUser # Django에서 제공하는 기본 User 모델 상속

'''User 모델 정의
AbstractUser: Django에서 제공하는 기본 User 모델, 개발자가 확장해서 사용할 수 있다.
username, password, email, first_name, last_name, date_joined 등의 필드를 이미 포함하고 있다.
'''

class User(AbstractUser): # User 모델을 AbstractUser 모델을 상속하며 정의
    # login_id는 AbstractUser의 username 필드를 사용
    # password는 AbstractUser에 이미 포함됨
    # created_at는 AbstractUser의 date_joined 필드를 사용
    
    nickname = models.CharField("닉네임", max_length=50, null=False, blank=False, default='default_nickname')
    updated_at = models.DateTimeField("수정일", auto_now=True)
    is_deleted = models.BooleanField("삭제여부", default=False)
    
    # 향후 역할 시스템을 위한 예시 필드들 (필요시 추가)
    # ROLE_CHOICES = [
    #     ('user', '일반사용자'),
    #     ('admin', '관리자'),
    #     ('moderator', '중간관리자'),
    # ]
    # role = models.CharField("역할", max_length=20, choices=ROLE_CHOICES, default='user')
    # is_premium = models.BooleanField("프리미엄 회원", default=False)
    
    # 기존 필드 제거
    # short_description = models.TextField("소개글", blank=True)
    
    '''Meta 클래스
    모델의 메타데이터를 정의하는 클래스
    즉, 모델 자체에 대한 설정을 지정하여 Django가 모델을 어떻게 처리할지 알려줌'''
    class Meta:
        db_table = 'users' # DB 테이블 이름을 users로 지정
        verbose_name = '사용자' # 관리자 페이지에서 보일 이름
        verbose_name_plural = '사용자들' # 복수형 이름
    
    def __str__(self):
        return f"{self.username} ({self.nickname})"
    
    # 유저 소프트 딜리트 기능
    def delete(self, using=None, keep_parents=False):
        """소프트 삭제 구현"""
        self.is_deleted = True
        self.save()
        
    def hard_delete(self, using=None, keep_parents=False):
        """실제 삭제"""
        super().delete(using=using, keep_parents=keep_parents)
