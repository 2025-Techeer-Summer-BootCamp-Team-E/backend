from django.urls import path
from .views import BookTextUploadView, BookFromPdfView, BookOfficialView, BookVideosView, BookCharactersView

urlpatterns = [
    path('text', BookTextUploadView.as_view()),
    path('pdf', BookFromPdfView.as_view()),
    path('official', BookOfficialView.as_view()),
    path('<int:book_id>/videos', BookVideosView.as_view()),
    path('<int:book_id>/characters', BookCharactersView.as_view()), 
]
