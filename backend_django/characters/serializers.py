from rest_framework import serializers
from .models import Character, CharacterScene

class CharacterSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterScene
        fields = ['id', 'scene_content', 'start_page', 'finish_page']

class CharacterSerializer(serializers.ModelSerializer):
    scenes = CharacterSceneSerializer(many=True, read_only=True)
    
    class Meta:
        model = Character
        fields = ['id', 'characterName', 'isMain', 'age', 'gender', 'characterDescription', 'scenes']

# Swagger 문서화를 위한 응답 Serializer들
class CharacterErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField(help_text="에러 메시지")

class CharacterDetailedErrorResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="에러 상태")
    error_code = serializers.IntegerField(help_text="에러 코드")
    message = serializers.CharField(help_text="에러 메시지")

class ScriptGenerateResponseSerializer(serializers.Serializer):
    script_id = serializers.CharField(help_text="생성된 스크립트 ID")
    characterId = serializers.IntegerField(help_text="캐릭터 ID")
    scenes = serializers.ListField(
        help_text="생성된 장면들",
        child=serializers.DictField(
            child=serializers.CharField(),
            help_text="장면 정보 (background, mood, style, camera, soundtrack, characters, lines, rewriting_prompt 등)"
        )
    ) 