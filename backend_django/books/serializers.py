# books/serializers.py
from rest_framework import serializers
from .models import Book

''' 소설 텍스트로 입력시 book 생성후 직렬화하는 함수 '''
class BookCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['id', 'title', 'content']

    def create(self, validated_data):
        return Book.objects.create(**validated_data)

''' PDF 파일로 입력시 book 생성후 직렬화하는 함수 '''
class BookPdfUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    pdf = serializers.FileField()

''' user_id가 requestbody로 갈거라고 생각하고 만들었는데 header로 받아야할 거 같아서 일단 숨김처리'''
# (요청 검증) 클라인트로부터 받은 user_id가 유효한지 검증
# class BookOfficialRequestSerializer(serializers.Serializer):
#    user_id = serializers.IntegerField()

#    def validate_user_id(self, value):
#     from users.models import User
#     if not User.objects.filter(id=value).exists():
#         raise serializers.ValidationError("존재하지 않는 사용자입니다.")
#     return value

# (응답용) DB에서 조회한 책 데이터를 JSON 형태로 변환
class BookOfficialResponseSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(source='id')
    title = serializers.CharField()
    content = serializers.CharField()
    pdf_url = serializers.SerializerMethodField()
    cover_url = serializers.URLField()
    
    def get_pdf_url(self, obj):
        """PDF URL을 Presigned URL로 반환하여 보안 강화"""
        if obj.pdf_url:
            try:
                from .s3_client import get_secure_pdf_url
                # 1시간 동안 유효한 Presigned URL 생성
                return get_secure_pdf_url(obj.pdf_url, expiration=3600)
            except Exception as e:
                # Presigned URL 생성 실패 시 원본 URL 반환 (fallback)
                print(f"[WARNING] Presigned URL 생성 실패: {str(e)}")
                return obj.pdf_url
        return None

class BookVideoResponseSerializer(serializers.Serializer):
    video_id=serializers.IntegerField(source='id')
    character_id=serializers.IntegerField(source='character.id')
    video_url = serializers.URLField(source='video_uri') # veo3Video 필드명
    thumbnail_url = serializers.URLField()

class BookCharacterResponseSerializer(serializers.Serializer):
    character_id = serializers.IntegerField(source='id')
    character_name = serializers.CharField(source='characterName')  # camelCase 필드명
    is_main = serializers.BooleanField(source='isMain')
    age = serializers.IntegerField()
    gender = serializers.CharField()
    character_description = serializers.CharField(source='characterDescription')

# 비동기 PDF 처리를 위한 응답 Serializer들
class BookAsyncUploadResponseSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(help_text="생성된 책 ID")
    title = serializers.CharField(help_text="책 제목")
    processing_status = serializers.CharField(help_text="처리 상태 (PENDING, PROCESSING, COMPLETED, FAILED)")
    task_id = serializers.CharField(help_text="Celery 태스크 ID", allow_null=True)
    message = serializers.CharField(help_text="상태 메시지")

class BookStatusResponseSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(help_text="책 ID")
    title = serializers.CharField(help_text="책 제목")
    processing_status = serializers.CharField(help_text="처리 상태")
    task_id = serializers.CharField(help_text="Celery 태스크 ID", allow_null=True)
    content = serializers.CharField(help_text="책 내용 요약", allow_null=True)
    pdf_url = serializers.SerializerMethodField(help_text="PDF 파일 Presigned URL", allow_null=True)
    cover_url = serializers.CharField(help_text="책 표지 이미지 URL", allow_null=True)
    error_message = serializers.CharField(help_text="오류 메시지", allow_null=True)
    created_at = serializers.DateTimeField(help_text="생성일시")
    updated_at = serializers.DateTimeField(help_text="수정일시")
    
    def get_pdf_url(self, obj):
        """PDF URL을 Presigned URL로 반환하여 보안 강화"""
        if hasattr(obj, 'pdf_url') and obj.pdf_url:
            try:
                from .s3_client import get_secure_pdf_url
                return get_secure_pdf_url(obj.pdf_url, expiration=3600)
            except Exception as e:
                print(f"[WARNING] Presigned URL 생성 실패: {str(e)}")
                return obj.pdf_url
        return None

# Swagger 문서화를 위한 응답 Serializer들
class BookErrorResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="에러 상태")
    error_code = serializers.IntegerField(help_text="에러 코드")
    message = serializers.CharField(help_text="에러 메시지")
    details = serializers.DictField(help_text="상세 에러 정보", required=False)

class BookSuccessResponseSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(help_text="책 ID")
    title = serializers.CharField(help_text="책 제목")
    content = serializers.CharField(help_text="책 내용 요약")
    pdf_url = serializers.SerializerMethodField(help_text="PDF 파일 Presigned URL", allow_null=True)
    cover_url = serializers.CharField(help_text="책 표지 이미지 URL", allow_null=True)
    
    def get_pdf_url(self, obj):
        """PDF URL을 Presigned URL로 반환하여 보안 강화"""
        if hasattr(obj, 'pdf_url') and obj.pdf_url:
            try:
                from .s3_client import get_secure_pdf_url
                return get_secure_pdf_url(obj.pdf_url, expiration=3600)
            except Exception as e:
                print(f"[WARNING] Presigned URL 생성 실패: {str(e)}")
                return obj.pdf_url
        return None