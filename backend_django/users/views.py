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
# from rest_framework_simplejwt.tokens import RefreshToken  # 기본 토큰 주석처리
from users.tokens import CustomRefreshToken  # 커스텀 토큰 사용
from users.serializers import LoginSerializer, SignupSerializer, UserSerializer

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
"""JWT 로그인 API"""
class LoginAPIView(APIView):
    # JWT 관련 인증 로직
    permission_classes = [AllowAny] # 누구나 접근 가능(로그인이기 때문에)
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # 여러 파서 지원
    
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


"""JWT 회원가입 API"""
class SignupAPIView(APIView):
    permission_classes = [AllowAny] # 누구나 접근 가능(회원가입 기능이므로)
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # 여러 파서 지원
    
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
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            'user': serializer.data
        }, status=status.HTTP_200_OK)
