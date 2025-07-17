from rest_framework import serializers
from .models import Video

# ModelSerializer는 Meta 클래스에 정의된 model (여기서는 Video 모델)을 기반으로 필드를 자동으로 생성
class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__' #  Video 모델에 있는 모든 필드를 포함하여 직렬화(serialization)하라는 의미입니다.
