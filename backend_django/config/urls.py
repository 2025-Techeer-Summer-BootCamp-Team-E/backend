"""
URL configuration for backend_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django_prometheus import exports

urlpatterns = [
    path('admin/', admin.site.urls),
    path("metrics", exports.ExportToDjangoView),

    path('books/', include('books.urls')),  # Books 애플리케이션의 URL 포함
    path('characters/', include('characters.urls')),  # Characters 애플리케이션의
    path('videos/', include('videos.urls')),  # Videos 애플리케이션의 URL 포함
]
