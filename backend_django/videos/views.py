from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import (
    start_text_to_image_task,
    start_image_to_video_task,
    get_task_status
)

class TextToImageTaskView(APIView):
    """API view to start a text-to-image generation task."""
    def post(self, request, *args, **kwargs):
        prompt = request.data.get('prompt')
        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)

        task_response = start_text_to_image_task(prompt)
        if "error" in task_response:
            return Response(task_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(task_response, status=status.HTTP_202_ACCEPTED)

class ImageToVideoTaskView(APIView):
    """API view to start an image-to-video generation task."""
    def post(self, request, *args, **kwargs):
        image_url = request.data.get('image_url')
        if not image_url:
            return Response({"error": "image_url is required"}, status=status.HTTP_400_BAD_REQUEST)

        task_response = start_image_to_video_task(image_url)
        if "error" in task_response:
            return Response(task_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(task_response, status=status.HTTP_202_ACCEPTED)

class TaskStatusView(APIView):
    """API view to check the status of any generation task."""
    def get(self, request, task_id, *args, **kwargs):
        status_response = get_task_status(task_id)
        if "error" in status_response:
            return Response(status_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status_response, status=status.HTTP_200_OK)