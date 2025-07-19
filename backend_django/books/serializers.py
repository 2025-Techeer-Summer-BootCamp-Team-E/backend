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
    
    def get_pdf_url(self, obj):
        # 현재 DB에 pdf_url 컬럼이 없으므로 임시 URL 반환
        return f"https://cdn.example.com/books/{obj.id}.pdf"
