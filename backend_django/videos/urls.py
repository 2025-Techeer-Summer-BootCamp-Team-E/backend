from django.urls import path
from .views import (
    TextToImageTaskView,
    ImageToVideoTaskView,
    TaskStatusView
)

urlpatterns = [
    path('generate-image/', TextToImageTaskView.as_view(), name='generate-image'),
    path('generate-video/', ImageToVideoTaskView.as_view(), name='generate-video'),
    path('tasks/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
]
