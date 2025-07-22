# 기존 Django 템플릿 뷰 관련 import들 (주석처리)
# from django.contrib.auth import authenticate, login, logout
# from django.shortcuts import render,redirect
# from users.forms import LoginForm, SignupForm
from users.models import User

# JWT API를 위한 import
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser  # 파서 추가
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
# from rest_framework_simplejwt.tokens import RefreshToken  # 기본 토큰 주석처리
from users.tokens import CustomRefreshToken  # 커스텀 토큰 사용
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
from django.views.decorators.csrf import csrf_exempt  # CSRF 면제 데코레이터 추가
from django.utils.decorators import method_decorator  # 클래스 기반 뷰에 데코레이터 적용
from users.serializers import (
    LoginSerializer, 
    SignupSerializer, 
    UserSerializer,
    JWTTokenResponseSerializer,
    JWTErrorResponseSerializer,
    UserInfoResponseSerializer
)

# Swagger 문서화를 위한 import
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# ========== 기존 템플릿 기반 뷰들 (주석처리) ==========
# def login_view(request):
#     # 사용자가 이미 로그인한 경우, 임시 페이지로 리다이렉트
#     if request.user.is_authenticated:
#         return redirect("/users/temp/")  # 임시 페이지로 리다이렉트

#     if request.method == 'POST':
#         # POST 요청인 경우, LoginForm 인스턴스를 만들어 사용자가 입력한 데이터를 전달. 입력데이터는 request.POST를 사용
#         form = LoginForm(data=request.POST)
#         # LoginForm에 들어온 데이터가 적절한지 유효성 검사
#         print("form.is_valid():",form.is_valid())

#         # LoginForm에 전달된 데이터가 유효한 경우, authenticate 함수를 사용하여 사용자 인증을 시도
#         if form.is_valid():
#             login_id = form.cleaned_data['login_id']
#             password = form.cleaned_data['password']

#             user = authenticate(request, username=login_id, password=password)

#             if user and not user.is_deleted:
#                 login(request,user)  # 사용자 인증 성공 시 로그인 처리
#                 return redirect("/users/temp/")  # 로그인 후 임시 페이지로 리다이렉트

#             else:
#                 # print("로그인에 실패했습니다.")  
#                 form.add_error(None,"입력한 자격증명에 해당하는 사용자가 없습니다.")

#         # 어떤 경우든 실패한 경우 (데이터 검증, 사용자 검사) 다시 LoginForm을 사용한 로그인 페이지 렌더링
#         context = {"form": form} 
#         return render(request, "users/login.html", context),
#     else:
#         # LoginForm 인스턴스를 생성
#         form = LoginForm()
        
#         # 생성한 LoginForm 인스턴스를 템플릿에 "form"이라는 키로 전달한다.
#         context = {
#             "form": form,
#         }

#         return render(request, "users/login.html", context)

# def logout_view(request):
#     logout(request)  # 로그아웃 처리
#     return redirect("/users/login/")  

# def signup(request):
#     # POST 요청시, form에 에러가 없다면(유효하다면) 곧바로 User를 생성하고 로그인 후 임시 페이지로 이동한다.
#     if request.method == 'POST':
#         form = SignupForm(data=request.POST, files=request.FILES)
        
#         if form.is_valid():
#             user = form.save()
      
#             login(request,user) 
#             return redirect("/users/temp/")  # 임시 페이지로 리다이렉트
    
#     # GET 요청 시, 빈 form을 생성한다.      
#     else:
#         form = SignupForm()

#     # POST 요청에서 form 이 유효하지 않다면, 여기로 이동.
#     # 결국 context로 전달되는 form은,
#     # 1. POST 요청에서 생성된 form 이 유효하지 않은 경우 > error를 포함한 form이 사용자에게 보여진다.
#     # 2. GET 요청으로 빈 form이 생성된 경우 -> 빈 form이 사용자에게 보여진다.
#     context = {
#         "form": form,
#     }
#     return render(request, "users/signup.html", context)

# def temp_view(request):
#     """임시 페이지 뷰"""
#     return render(request, "users/temp.html")


# ========== JWT API 뷰들 ==========
@method_decorator(csrf_exempt, name='dispatch')
class LoginAPIView(APIView):
    """JWT 로그인 API"""
    permission_classes = [AllowAny] # 누구나 접근 가능(로그인이기 때문에)
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # 여러 파서 지원
    
    @swagger_auto_schema(
        operation_description="""JWT 토큰 기반 로그인 API
        
        사용자의 로그인 ID와 비밀번호를 검증하고, 성공 시 JWT 액세스 토큰과 리프레시 토큰을 발급합니다.
        
        **토큰 사용법:**
        - 발급받은 access_token을 Authorization 헤더에 Bearer 방식으로 포함
        - 예시: `Authorization: Bearer {access_token}`
        
        **토큰 만료:**
        - Access Token: 60분 (개발환경) / 60분 (프로덕션)
        - Refresh Token: 7일 (개발환경) / 1일 (프로덕션)
        
        **Payload 정보:**
        - login_id: 사용자 로그인 ID
        - nickname: 사용자 닉네임
        - created_at: 계정 생성일
        - last_login: 마지막 로그인 시간
        """,
        request_body=LoginSerializer,
        responses={
            200: JWTTokenResponseSerializer,
            400: JWTErrorResponseSerializer
        },
        tags=['인증 (Authentication)'],
        examples={
            'application/json': {
                'login_id': 'testuser',
                'password': 'testpass123!'
            }
        }
    )
    def post(self, request):
        '''login_id와 password의 유효성을 검사하고 직렬화'''
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # JWT 토큰 생성, 커스텀 토큰 사용
            refresh = CustomRefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # 응답결과로 token과 user 정보를 반환
            return Response({
                'message': '로그인 성공',
                'access_token': str(access_token),
                'refresh_token': str(refresh),
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': '로그인 실패',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class SignupAPIView(APIView):
    """JWT 회원가입 API"""
    permission_classes = [AllowAny] # 누구나 접근 가능(회원가입 기능이므로)
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # 여러 파서 지원
    
    @swagger_auto_schema(
        operation_description="""JWT 토큰 기반 회원가입 API
        
        새로운 사용자 계정을 생성하고, 성공 시 자동으로 JWT 토큰을 발급하여 로그인 상태로 만듭니다.
        
        **필수 입력 정보:**
        - login_id: 로그인 ID (중복 불가)
        - password: 비밀번호 (Django 기본 검증 규칙 적용)
        - password_confirm: 비밀번호 확인
        - nickname: 사용자 닉네임
        
        **비밀번호 규칙:**
        - 최소 8자 이상
        - 숫자, 문자, 특수문자 조합 권장
        - 사용자 정보와 너무 유사하면 안됨
        
        **회원가입 후 자동 로그인:**
        회원가입이 성공하면 자동으로 JWT 토큰이 발급되어 별도 로그인 없이 바로 서비스 이용 가능합니다.
        """,
        request_body=SignupSerializer,
        responses={
            201: JWTTokenResponseSerializer,
            400: JWTErrorResponseSerializer
        },
        tags=['인증 (Authentication)'],
        examples={
            'application/json': {
                'login_id': 'newuser',
                'password': 'newpass123!',
                'password_confirm': 'newpass123!',
                'nickname': '새로운유저'
            }
        }
    )
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # 회원가입 후 자동으로 JWT 토큰 생성
            refresh = CustomRefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                'message': '회원가입 성공',
                'access_token': str(access_token),
                'refresh_token': str(refresh),
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': '회원가입 실패',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserInfoAPIView(APIView):
    """사용자 정보 조회 API (JWT 인증 필요)"""
    permission_classes = [IsAuthenticated] # JWT 인증이 필요한 API
    
    @swagger_auto_schema(
        operation_description="""JWT 인증된 사용자 정보 조회 API
        
        현재 로그인한 사용자의 정보를 조회합니다.
        
        **인증 방법:**
        - Authorization 헤더에 Bearer 토큰 포함 필수
        - 예시: `Authorization: Bearer {access_token}`
        
        **조회 가능한 정보:**
        - id: 사용자 고유 ID
        - login_id: 로그인 ID
        - nickname: 닉네임
        - created_at: 계정 생성일
        - updated_at: 정보 수정일
        
        **주의사항:**
        - 토큰이 만료된 경우 401 Unauthorized 응답
        - 잘못된 토큰인 경우 401 Unauthorized 응답
        """,
        responses={
            200: UserInfoResponseSerializer,
            401: openapi.Response(
                description="인증 실패", 
                examples={
                    "application/json": {
                        "detail": "자격 인증데이터(authentication credentials)가 제공되지 않았습니다."
                    }
                }
            )
        },
        tags=['사용자 정보']
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            'user': serializer.data
        }, status=status.HTTP_200_OK)


class CustomTokenRefreshView(TokenRefreshView):
    """JWT 토큰 갱신 API (Swagger 문서화 포함)"""
    
    @swagger_auto_schema(
        operation_description="""JWT 토큰 갱신 API
        
        만료된 Access Token을 새로운 Access Token으로 갱신합니다.
        
        **사용 시나리오:**
        - Access Token이 만료되었을 때 (401 Unauthorized 응답 시)
        - 로그아웃 없이 지속적인 서비스 이용을 위해
        
        **갱신 과정:**
        1. 로그인/회원가입 시 받은 refresh_token을 요청 Body에 포함
        2. 서버에서 refresh_token 검증
        3. 유효한 경우 새로운 access_token 발급
        4. 설정에 따라 새로운 refresh_token도 함께 발급 (ROTATE_REFRESH_TOKENS=True)
        
        **토큰 순환 정책:**
        - ROTATE_REFRESH_TOKENS=True: 갱신 시 새로운 refresh_token도 발급
        - BLACKLIST_AFTER_ROTATION=True: 기존 refresh_token 무효화
        
        **주의사항:**
        - refresh_token이 만료된 경우 다시 로그인 필요
        - 잘못된 refresh_token인 경우 401 Unauthorized 응답
        """,
        request_body=TokenRefreshSerializer,
        responses={
            200: openapi.Response(
                description="토큰 갱신 성공",
                examples={
                    "application/json": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."  # ROTATE_REFRESH_TOKENS=True인 경우만
                    }
                }
            ),
            401: openapi.Response(
                description="토큰 갱신 실패",
                examples={
                    "application/json": {
                        "detail": "토큰이 잘못되었거나 만료되었습니다.",
                        "code": "token_not_valid"
                    }
                }
            )
        },
        tags=['인증 (Authentication)'],
        examples={
            'application/json': {
                'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
            }
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class LogoutAPIView(APIView):
    """JWT 로그아웃 API"""
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 가능
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    @swagger_auto_schema(
        operation_description="""JWT 토큰 기반 로그아웃 API
        
        현재 사용 중인 JWT 토큰을 무효화하여 로그아웃 처리합니다.
        
        **로그아웃 과정:**
        1. Authorization 헤더의 Access Token으로 사용자 인증
        2. 요청 Body의 refresh_token을 블랙리스트에 추가
        3. 해당 토큰으로는 더 이상 API 접근 불가
        
        **토큰 무효화 방식:**
        - **Refresh Token**: 블랙리스트에 추가하여 완전히 무효화
        - **Access Token**: 만료 시간까지는 유효하지만 새로운 토큰 발급 불가
        
        **보안 강화:**
        - 토큰 탈취 시 즉시 무효화 가능
        - 다중 기기 로그인 시 특정 기기만 로그아웃 가능
        
        **클라이언트 처리:**
        로그아웃 성공 후 클라이언트에서는:
        1. 로컬 저장소의 토큰 삭제 (localStorage, sessionStorage 등)
        2. Authorization 헤더 제거
        3. 로그인 페이지로 리다이렉트
        
        **주의사항:**
        - refresh_token이 이미 블랙리스트에 있는 경우에도 성공 응답
        - 잘못된 refresh_token인 경우 400 Bad Request 응답
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh_token': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='로그아웃할 refresh token'
                )
            },
            required=['refresh_token']
        ),
        responses={
            200: openapi.Response(
                description="로그아웃 성공",
                examples={
                    "application/json": {
                        "message": "로그아웃 되었습니다.",
                        "detail": "토큰이 성공적으로 무효화되었습니다."
                    }
                }
            ),
            400: openapi.Response(
                description="로그아웃 실패",
                examples={
                    "application/json": {
                        "message": "로그아웃 실패",
                        "error": "유효하지 않은 refresh token입니다."
                    }
                }
            ),
            401: openapi.Response(
                description="인증 실패",
                examples={
                    "application/json": {
                        "detail": "자격 인증데이터(authentication credentials)가 제공되지 않았습니다."
                    }
                }
            )
        },
        tags=['인증 (Authentication)'],
        examples={
            'application/json': {
                'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
            }
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            
            if not refresh_token:
                return Response({
                    'message': '로그아웃 실패',
                    'error': 'refresh_token이 필요합니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # RefreshToken 객체 생성 및 블랙리스트 추가
            token = CustomRefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': '로그아웃 되었습니다.',
                'detail': '토큰이 성공적으로 무효화되었습니다.'
            }, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response({
                'message': '로그아웃 실패', 
                'error': '유효하지 않은 refresh token입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'message': '로그아웃 실패',
                'error': '서버 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutAllAPIView(APIView):
    """모든 기기에서 로그아웃 API"""
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    @swagger_auto_schema(
        operation_description="""모든 기기에서 JWT 로그아웃 API
        
        현재 사용자의 모든 Outstanding Token을 블랙리스트에 추가하여 
        모든 기기에서 로그아웃 처리합니다.
        
        **사용 시나리오:**
        - 보안상 이유로 모든 기기에서 즉시 로그아웃 필요한 경우
        - 비밀번호 변경 후 보안 강화
        - 계정 해킹 의심 시 긴급 조치
        
        **처리 과정:**
        1. 현재 사용자의 모든 Outstanding Token 조회
        2. 아직 블랙리스트에 없는 토큰들을 모두 블랙리스트에 추가
        3. 모든 기기에서 즉시 API 접근 불가
        
        **영향 범위:**
        - 웹 브라우저, 모바일 앱 등 모든 플랫폼
        - 현재 기기 포함 모든 기기에서 재로그인 필요
        
        **주의사항:**
        - 이 API 호출 후 현재 세션도 무효화됨
        - 재로그인 필요
        """,
        responses={
            200: openapi.Response(
                description="전체 로그아웃 성공",
                examples={
                    "application/json": {
                        "message": "모든 기기에서 로그아웃 되었습니다.",
                        "detail": "총 3개의 토큰이 무효화되었습니다."
                    }
                }
            ),
            401: openapi.Response(
                description="인증 실패",
                examples={
                    "application/json": {
                        "detail": "자격 인증데이터(authentication credentials)가 제공되지 않았습니다."
                    }
                }
            )
        },
        tags=['인증 (Authentication)']
    )
    def post(self, request):
        try:
            # 현재 사용자의 모든 Outstanding Token 조회
            outstanding_tokens = OutstandingToken.objects.filter(user=request.user)
            
            blacklisted_count = 0
            for outstanding_token in outstanding_tokens:
                # 이미 블랙리스트에 있지 않은 토큰만 블랙리스트에 추가
                if not BlacklistedToken.objects.filter(token=outstanding_token).exists():
                    BlacklistedToken.objects.create(token=outstanding_token)
                    blacklisted_count += 1
            
            return Response({
                'message': '모든 기기에서 로그아웃 되었습니다.',
                'detail': f'총 {blacklisted_count}개의 토큰이 무효화되었습니다.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'message': '전체 로그아웃 실패',
                'error': '서버 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
