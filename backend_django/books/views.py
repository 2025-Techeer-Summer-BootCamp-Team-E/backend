from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from books.pdf_utils import extract_text_from_pdf # pdf 파일에서 텍스트를 추출하는 함수
from books.gpt_client import summarize_with_gpt # GPT를 이용한 pdf 책 요약 함수
from books.s3_client import upload_to_s3 # S3에 파일을 업로드하는 함수
from .serializers import BookCreateSerializer, BookPdfUploadSerializer, BookOfficialResponseSerializer, BookVideoResponseSerializer,  BookCharacterResponseSerializer 
from .models import Book
from voe3Video.models import Video
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


class BookOfficialView(APIView):
    def get(self, request):
        # 1. 삭제되지 않은 모든 책 조회 (user_id 검증 없이)
        #books = Book.objects.filter(is_deleted=False
        # 1. 삭제되지 않은 모든 책 조회 (존재하는 필드만 선택)
        books = Book.objects.filter(is_deleted=False).only('id', 'title', 'content')
        
        # 2. 응답 데이터 직렬화
        response_serializer = BookOfficialResponseSerializer(books, many=True)
        
        # 3. 성공 응답 반환
        return Response(response_serializer.data, status=status.HTTP_200_OK)

class BookVideosView(APIView):
    def get(self, request, book_id):
        try:
            # 1. 책 존재 여부 확인
            book = Book.objects.get(id=book_id, is_deleted=False)
            
            # 2. 해당 책의 캐릭터들 조회
            characters = book.characters.filter(is_deleted=False)

            # 3. 캐릭터들의 비디오들 조회
            videos = Video.objects.filter(character__in=characters)

            # 4. 응답 데이터 직렬화
            serializer = BookVideoResponseSerializer(videos, many=True)
            return Response(serializer.data, status=200)
            
        except Book.DoesNotExist:
            return Response({
                "status": "error",
                "error_code": 404,
                "message": "책을 찾을 수 없습니다."
            }, status=404)
        except Exception as e:
            return Response({
                "status": "error",
                "error_code": 500,
                "message": "서버 내부 오류가 발생했습니다."
            }, status=500)

class BookCharactersView(APIView):
    def get(self, request, book_id): 
        try:
            # 1. 책 존재 여부 확인
            book = Book.objects.get(id=book_id, is_deleted=False)
            
            # 2. 해당 책의 캐릭터들 조회
            characters = book.characters.filter(is_deleted=False)

            # 3. 응답 데이터 직렬화
            serializer = BookCharacterResponseSerializer(characters, many=True)
            return Response(serializer.data, status=200)  
            
        except Book.DoesNotExist:
            return Response({
                "status": "error",
                "error_code": 404,
                "message": "책을 찾을 수 없습니다."
            }, status=404)
        except Exception as e:
            return Response({
                "status": "error",
                "error_code": 500,
                "message": "서버 내부 오류가 발생했습니다."
            }, status=500)