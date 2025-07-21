from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime

"""커스텀 RefreshToken - payload에 추가 사용자 정보 포함"""
class CustomRefreshToken(RefreshToken):
    
    @classmethod
    def for_user(cls, user):
        """사용자를 위한 토큰 생성 시 추가 payload에 사용자 정보 포함
        """

        token = super().for_user(user)
        """
        for_user() 함수
        payload에서 userId를 기본적으로 구성해줍니다!
        @classmethod
        def for_user(cls, user):
            token = cls()
            token[api_settings.USER_ID_CLAIM] = getattr(user, api_settings.USER_ID_FIELD)
            return token
        """
        
        # 기본적으로 토큰에 넣는 사용자 정보
        token['login_id'] = user.username
        token['is_deleted'] = user.is_deleted
        # token['nickname'] = user.nickname
        
        # 계정 생성일 (ISO 형식)
        # token['created_at'] = user.date_joined.isoformat()
        
        # 마지막 로그인 시간 (있는 경우)
        if user.last_login:
            token['last_login'] = user.last_login.isoformat()
        
        # 향후 역할 시스템이 있다면 추가 가능
        # token['role'] = user.role if hasattr(user, 'role') else 'user'
        # token['is_premium'] = user.is_premium if hasattr(user, 'is_premium') else False
        # token['permissions'] = list(user.get_all_permissions()) if user.is_authenticated else []
        
        # 추가 메타데이터
        # token['token_version'] = 'v1'  # 토큰 버전 관리
        # token['device_info'] = request.META.get('HTTP_USER_AGENT', '')[:100] if hasattr(cls, '_request') else ''
        
        return token


class CustomAccessToken(RefreshToken.access_token_class):
    """커스텀 AccessToken - RefreshToken에서 상속받은 payload 정보 포함"""
    pass


# RefreshToken의 access_token_class를 커스텀으로 변경
CustomRefreshToken.access_token_class = CustomAccessToken 
