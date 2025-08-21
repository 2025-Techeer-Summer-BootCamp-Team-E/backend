# from rest_framework import serializers
# from .models import Video
# # veo3Video/serializers.py : 데이터 변환 계층
# # ModelSerializer는 Meta 클래스에 정의된 model (여기서는 Video 모델)을 기반으로 필드를 자동으로 생성
# # 즉, Video모델의 필드들을 정의 Video 객체를 JSON으로 변환하거나 JSON 데이터를 Video객체로 생성/업데이트 할 때 사용
# class VideoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Video
#         fields = '__all__' #  Video 모델에 있는 모든 필드를 포함하여 직렬화(serialization)하라는 의미입니다.

# # GET /videos/{videoId} API를 위한 응답 Serializer
# class VideoDetailSerializer(serializers.ModelSerializer):
#     video_id = serializers.IntegerField(source='id', read_only=True)
#     video_title = serializers.CharField(source='title', read_only=True)
#     video_url = serializers.CharField(source='video_uri', read_only=True, allow_null=True)
#     thumbnail_url = serializers.CharField(read_only=True, allow_null=True)
    
#     class Meta:
#         model = Video
#         fields = ['video_id', 'video_title', 'video_url', 'thumbnail_url']

# # 에러 응답을 위한 Serializer
# class VideoErrorResponseSerializer(serializers.Serializer):
#     status = serializers.CharField(help_text="에러 상태")
#     error_code = serializers.IntegerField(help_text="에러 코드")
#     message = serializers.CharField(help_text="에러 메시지")
