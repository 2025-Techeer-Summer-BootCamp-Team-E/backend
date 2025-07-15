from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render,redirect
from users.forms import LoginForm, SignupForm
from users.models import User

def login_view(request):
    # 사용자가 이미 로그인한 경우, 임시 페이지로 리다이렉트
    if request.user.is_authenticated:
        return redirect("/users/temp/")  # 임시 페이지로 리다이렉트

    if request.method == 'POST':
        # POST 요청인 경우, LoginForm 인스턴스를 만들어 사용자가 입력한 데이터를 전달. 입력데이터는 request.POST를 사용
        form = LoginForm(data=request.POST)
        # LoginForm에 들어온 데이터가 적절한지 유효성 검사
        print("form.is_valid():",form.is_valid())

        # LoginForm에 전달된 데이터가 유효한 경우, authenticate 함수를 사용하여 사용자 인증을 시도
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user:
                login(request,user)  # 사용자 인증 성공 시 로그인 처리
                return redirect("/users/temp/")  # 로그인 후 임시 페이지로 리다이렉트

            else:
                # print("로그인에 실패했습니다.")  
                form.add_error(None,"입력한 자격증명에 해당하는 사용자가 없습니다.")

        # 어떤 경우든 실패한 경우 (데이터 검증, 사용자 검사) 다시 LoginForm을 사용한 로그인 페이지 렌더링
        context = {"form": form} 
        return render(request, "users/login.html", context),
    else:
        # LoginForm 인스턴스를 생성
        form = LoginForm()
        
        # 생성한 LoginForm 인스턴스를 템플릿에 "form"이라는 키로 전달한다.
        context = {
            "form": form,
        }

        return render(request, "users/login.html", context)

def logout_view(request):
    logout(request)  # 로그아웃 처리
    return redirect("/users/login/")  

def signup(request):
    # POST 요청시, form에 에러가 없다면(유효하다면) 곧바로 User를 생성하고 로그인 후 임시 페이지로 이동한다.
    if request.method == 'POST':
        form = SignupForm(data=request.POST, files=request.FILES)
        
        if form.is_valid():
            user = form.save()
      
            login(request,user) 
            return redirect("/users/temp/")  # 임시 페이지로 리다이렉트
    
    # GET 요청 시, 빈 form을 생성한다.      
    else:
        form = SignupForm()

    # POST 요청에서 form 이 유효하지 않다면, 여기로 이동.
    # 결국 context로 전달되는 form은,
    # 1. POST 요청에서 생성된 form 이 유효하지 않은 경우 > error를 포함한 form이 사용자에게 보여진다.
    # 2. GET 요청으로 빈 form이 생성된 경우 -> 빈 form이 사용자에게 보여진다.
    context = {
        "form": form,
    }
    return render(request, "users/signup.html", context)