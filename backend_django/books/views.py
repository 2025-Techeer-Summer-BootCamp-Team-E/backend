from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from books.pdf_utils import extract_text_from_pdf # pdf 파일에서 텍스트를 추출하는 함수
from books.gpt_client import summarize_with_gpt # GPT를 이용한 pdf 책 요약 함수
from books.s3_client import upload_to_s3 # S3에 파일을 업로드하는 함수
from .serializers import BookCreateSerializer, BookPdfUploadSerializer
from .models import Book

# Create your views here.

# 책 입력 API 2가지를 정의함
# 나중에 구현할 기능이기에 추후에 수정이 반드시 필요!!
''' 책 텍스트로 입력시 book을 생성하는 API '''
class BookTextUploadView(APIView):
    def post(self, request):
        serializer = BookCreateSerializer(data=request.data)
        if serializer.is_valid():
            book = serializer.save()
            return Response({
                "book_id": book.id,
                "title": book.title,
                "content": book.content,
                "book_url": None
            }, status=status.HTTP_201_CREATED)
        return Response({
            "status": "error",
            "error_code": 400,
            "message": "입력한 정보 형식이 올바르지 않습니다."
        }, status=status.HTTP_400_BAD_REQUEST)
    

class BookFromPdfView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = BookPdfUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": "error",
                "error_code": 400,
                "message": "입력 형식이 올바르지 않습니다."
            }, status=400)

        title = serializer.validated_data['title']
        pdf_file = serializer.validated_data['pdf']

        try:
            # 1. PDF 텍스트 추출
            extracted_text = extract_text_from_pdf(pdf_file)

            # 2. GPT 요약
            summary = summarize_with_gpt(extracted_text)

            # 3. S3 업로드 => pdf_URL을 얻어냄
            pdf_file.seek(0)
            pdf_url = upload_to_s3(pdf_file)  # 구현 안 했으면 pdf_url = None 로 대체 가능

            # 4. DB 저장
            book = Book.objects.create(
                title=title,
                content=summary,
                pdf_url=pdf_url
            )

            return Response({
                "book_id": book.id,
                "title": book.title,
                "content": book.content,
                "pdf_url": book.pdf_url
            }, status=201)

        except Exception as e:
            print("[ERROR]", e)
            return Response({
                "status": "error",
                "error_code": 500,
                "message": "PDF 처리 중 오류가 발생했습니다."
            }, status=500)

