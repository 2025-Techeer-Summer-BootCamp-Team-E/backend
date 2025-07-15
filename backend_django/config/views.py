from django.shortcuts import redirect

def index(request):
    # 사용자가 이미 로그인한 경우, 임시 페이지로 리다이렉트
    if request.user.is_authenticated:
        return redirect("/users/temp/")
    # 사용자가 인증되지 않은 경우, 로그인 페이지로 리다이렉트
    else:
        return redirect("/users/login/")
