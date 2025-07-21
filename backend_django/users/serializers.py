from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from users.models import User

'''로그인 요청을 처리하는 직렬화 클래스'''
class LoginSerializer(serializers.Serializer):
    """로그인용 Serializer"""
    # 사용자에게 login_id와 비밀번호를 입력받음
    login_id = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    '''사용자가 입력한 login_id, password의 유효성 검사'''
    def validate(self, attrs):
        login_id = attrs.get('login_id')
        password = attrs.get('password')
        
        if login_id and password: # login_id와 password를 입력받았을때
            # authenticate(): login_id와 password로 로그인하고, 유저를 인증처리하는 함수
            user = authenticate(username=login_id, password=password) # login_id는 username 필드에 매핑됨
            # 입력한 login_id, password가 잘못되었을때
            if not user:
                raise serializers.ValidationError('잘못된 로그인 ID 또는 비밀번호입니다.')
            # 이전에 비활성화된 유저일때
            if not user.is_active:
                raise serializers.ValidationError('비활성화된 계정입니다.')
            # 이전에 소프트 딜리트된 유저일때
            if user.is_deleted:
                raise serializers.ValidationError('삭제된 계정입니다.')
            attrs['user'] = user
            return attrs
        else:
            # login_id나 password 둘 중 하나를 입력하지 않았을 경우
            raise serializers.ValidationError('로그인 ID와 비밀번호를 모두 입력해주세요.')


class SignupSerializer(serializers.ModelSerializer):
    """회원가입용 Serializer"""
    # 사용자에게 입력받을 속성
    login_id = serializers.CharField(source='username')
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['login_id', 'password', 'password_confirm', 'nickname']
        
    """로그인 ID 중복 검증"""
    def validate_login_id(self, value):
        if User.objects.filter(username=value, is_deleted=False).exists():
            raise serializers.ValidationError('이미 사용 중인 로그인 ID입니다.')
        return value
        
    '''입력한 패스워드가 일치하는지 확인하는 함수'''
    def validate(self, attrs):
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        if password != password_confirm:
            raise serializers.ValidationError('비밀번호가 일치하지 않습니다.')
        
        return attrs
    
    def create(self, validated_data):
        # password_confirm은 사용하지 않으므로 제거
        validated_data.pop('password_confirm', None)
        
        user = User.objects.create_user(
            username=validated_data['username'],  # login_id가 username으로 매핑됨
            password=validated_data['password'],
            nickname=validated_data['nickname']
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """사용자 정보용 Serializer"""
    login_id = serializers.CharField(source='username', read_only=True)
    created_at = serializers.DateTimeField(source='date_joined', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'login_id', 'nickname', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at'] 


# ========== Swagger 문서화를 위한 응답 Serializer들 ==========

class JWTTokenResponseSerializer(serializers.Serializer):
    """JWT 토큰 응답용 Serializer (로그인/회원가입 성공 시)"""
    message = serializers.CharField(help_text="결과 메시지")
    access_token = serializers.CharField(help_text="JWT 액세스 토큰 (Bearer 방식으로 사용)")
    refresh_token = serializers.CharField(help_text="JWT 리프레시 토큰 (토큰 갱신용)")
    user = UserSerializer(help_text="사용자 정보")

    class Meta:
        examples = {
            "message": "로그인 성공",
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "user": {
                "id": 1,
                "login_id": "testuser",
                "nickname": "테스트유저",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z"
            }
        }


class JWTErrorResponseSerializer(serializers.Serializer):
    """JWT 에러 응답용 Serializer"""
    message = serializers.CharField(help_text="에러 메시지")
    errors = serializers.DictField(help_text="상세 에러 정보", required=False)

    class Meta:
        examples = {
            "message": "로그인 실패",
            "errors": {
                "non_field_errors": ["잘못된 로그인 ID 또는 비밀번호입니다."]
            }
        }


class UserInfoResponseSerializer(serializers.Serializer):
    """사용자 정보 조회 응답용 Serializer"""
    user = UserSerializer(help_text="인증된 사용자 정보")

    class Meta:
        examples = {
            "user": {
                "id": 1,
                "login_id": "testuser",
                "nickname": "테스트유저",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z"
            }
        } 
