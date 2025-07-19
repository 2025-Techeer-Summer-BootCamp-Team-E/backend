from django.urls import path
from .views import BookTextUploadView, BookFromPdfView, BookOfficialView

urlpatterns = [
    path('text', BookTextUploadView.as_view()),
    path('pdf', BookFromPdfView.as_view()),
    path('official', BookOfficialView.as_view()),


]
