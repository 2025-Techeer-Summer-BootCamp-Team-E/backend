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