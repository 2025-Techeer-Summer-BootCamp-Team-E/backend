from rest_framework import serializers
from .models import Character, CharacterScene

class CharacterSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterScene
        fields = ['id', 'scene_content', 'start_page', 'finish_page']

class CharacterSimpleSerializer(serializers.ModelSerializer):
    """Scenes 없이 캐릭터 기본 정보만 반환하는 Serializer"""
    
    class Meta:
        model = Character
        fields = ['id', 'characterName', 'isMain', 'age', 'gender', 'characterDescription']

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

# 비동기 대본 생성을 위한 응답 Serializer들 (Redis 기반)
class ScriptAsyncResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField(help_text="Celery 태스크 ID")
    character_id = serializers.IntegerField(help_text="캐릭터 ID")
    character_name = serializers.CharField(help_text="캐릭터 이름")
    scene_count = serializers.IntegerField(help_text="생성할 장면 수")
    message = serializers.CharField(help_text="상태 메시지")

class ScriptTaskStatusResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField(help_text="Celery 태스크 ID")
    character_id = serializers.IntegerField(help_text="캐릭터 ID")
    character_name = serializers.CharField(help_text="캐릭터 이름", allow_null=True)
    status = serializers.CharField(help_text="처리 상태 (PROCESSING, COMPLETED, FAILED)")
    script_id = serializers.CharField(help_text="완성된 스크립트 ID", allow_null=True)
    scene_count = serializers.IntegerField(help_text="생성할 장면 수")
    scenes = serializers.ListField(
        help_text="완성된 대본 장면들 (COMPLETED 상태일 때만 포함)",
        child=serializers.DictField(
            child=serializers.CharField(),
            help_text="장면 정보 (background, mood, style, camera, soundtrack, characters, rewriting_prompt 등)"
        ),
        required=False,
        allow_null=True
    )
    error_message = serializers.CharField(help_text="오류 메시지", allow_null=True)
    message = serializers.CharField(help_text="상태 메시지", allow_null=True)
    started_at = serializers.CharField(help_text="시작일시", allow_null=True)
    completed_at = serializers.CharField(help_text="완료일시", allow_null=True)
    failed_at = serializers.CharField(help_text="실패일시", allow_null=True)

# 비동기 캐릭터 생성을 위한 응답 Serializer들
class CharacterAsyncResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField(help_text="Celery 태스크 ID")
    book_id = serializers.IntegerField(help_text="책 ID")
    book_title = serializers.CharField(help_text="책 제목")
    message = serializers.CharField(help_text="상태 메시지")

class CharacterTaskStatusResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField(help_text="Celery 태스크 ID")
    book_id = serializers.IntegerField(help_text="책 ID")
    book_title = serializers.CharField(help_text="책 제목", allow_null=True)
    status = serializers.CharField(help_text="처리 상태 (PROCESSING, COMPLETED, FAILED)")
    step = serializers.CharField(help_text="현재 처리 단계", allow_null=True)
    message = serializers.CharField(help_text="상태 메시지", allow_null=True)
    
    # 진행률 정보
    total_chunks = serializers.IntegerField(help_text="총 청크 수", allow_null=True)
    processed_chunks = serializers.IntegerField(help_text="처리된 청크 수", allow_null=True)
    current_chunk = serializers.IntegerField(help_text="현재 처리 중인 청크", allow_null=True)
    total_characters = serializers.IntegerField(help_text="총 캐릭터 수", allow_null=True)
    processed_characters = serializers.IntegerField(help_text="처리된 캐릭터 수", allow_null=True)
    current_character = serializers.CharField(help_text="현재 처리 중인 캐릭터", allow_null=True)
    
    # 결과 정보 (완료 시에만)
    characters = serializers.ListField(
        help_text="생성된 캐릭터 목록 (COMPLETED 상태일 때만 포함)",
        child=CharacterSerializer(),
        required=False,
        allow_null=True
    )
    processing_stats = serializers.DictField(
        help_text="처리 통계 정보",
        required=False,
        allow_null=True
    )
    
    # 오류 정보
    error_message = serializers.CharField(help_text="오류 메시지", allow_null=True)
    
    # 시간 정보
    started_at = serializers.CharField(help_text="시작일시", allow_null=True)
    completed_at = serializers.CharField(help_text="완료일시", allow_null=True)
    failed_at = serializers.CharField(help_text="실패일시", allow_null=True)