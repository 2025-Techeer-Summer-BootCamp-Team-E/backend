from django.urls import path
from .views import BookTextUploadView, BookFromPdfView

urlpatterns = [
    path('text', BookTextUploadView.as_view()),
    path('pdf', BookFromPdfView.as_view()),


]
