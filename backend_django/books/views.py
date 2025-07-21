# books/views.py

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated  # JWT 인증 추가
from books.pdf_utils import extract_text_from_pdf # pdf 파일에서 텍스트를 추출하는 함수
from books.gemini_client import summarize_with_gemini # Gemini를 이용한 pdf 책 요약 함수
from books.s3_client import upload_to_s3 # S3에 파일을 업로드하는 함수
from .serializers import (
    BookCreateSerializer, 
    BookPdfUploadSerializer, 
    BookOfficialResponseSerializer, 
    BookVideoResponseSerializer,  
    BookCharacterResponseSerializer,
    BookErrorResponseSerializer,
    BookSuccessResponseSerializer
)
from .models import Book
from voe3Video.models import Video
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
# Create your views here.

# 책 입력 API 2가지를 정의함
''' 책 텍스트로 입력시 book을 생성하는 API '''
class BookTextUploadView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="텍스트로 책을 생성합니다. (JWT 인증 필요)",
        request_body=BookCreateSerializer,
        responses={
            201: BookSuccessResponseSerializer,
            400: BookErrorResponseSerializer,
            401: openapi.Response(description="인증 필요")
        },
        tags=['책 관리']
    )
    def post(self, request):
        serializer = BookCreateSerializer(data=request.data)
        if serializer.is_valid():
            # 책 생성 (user 외래키 없음)
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
            "message": "입력한 정보 형식이 올바르지 않습니다.",
            "details": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    

class BookFromPdfView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]  # JWT 인증 필요

    @swagger_auto_schema(
        operation_description="""PDF 파일을 업로드하여 책을 생성합니다. (JWT 인증 필요)
        
        처리 과정:
        1. PDF에서 텍스트 추출 (텍스트 기반 또는 OCR)
        2. Gemini API로 내용 요약
        3. S3에 PDF 파일 업로드
        4. DB에 책 정보 저장
        
        가능한 오류:
        - 400: PDF 파일 누락, 잘못된 형식
        - 401: 인증 필요
        - 500: PDF 파싱 실패, API 오류, S3 업로드 실패
        """,
        manual_parameters=[
            openapi.Parameter(
                'title',
                openapi.IN_FORM,
                description="책 제목",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'pdf',
                openapi.IN_FORM,
                description="PDF 파일",
                type=openapi.TYPE_FILE,
                required=True
            ),
        ],
        responses={
            201: BookSuccessResponseSerializer,
            400: BookErrorResponseSerializer,
            401: openapi.Response(description="인증 필요"),
            500: BookErrorResponseSerializer
        },
        tags=['책 관리']
    )
    def post(self, request):
        print("📝 PDF 업로드 요청 데이터:", request.data)
        print("👤 요청 사용자:", request.user.username if request.user.is_authenticated else "익명")
        print("📁 파일 목록:", request.FILES)
        print("🔍 요청 헤더 Content-Type:", request.content_type)
        print("🔍 요청 메소드:", request.method)
        
        # 파일 업로드 상세 디버깅
        if 'pdf' in request.FILES:
            pdf_file = request.FILES['pdf']
            print(f"✅ PDF 파일 감지: {pdf_file.name}, 크기: {pdf_file.size} bytes")
        else:
            print("❌ PDF 파일이 request.FILES에 없습니다.")
            print("🔍 사용 가능한 키들:", list(request.FILES.keys()))
        
        serializer = BookPdfUploadSerializer(data=request.data)
        if not serializer.is_valid():
            print("❌ Serializer 검증 실패:", serializer.errors)
            return Response({
                "status": "error",
                "error_code": 400,
                "message": "입력 형식이 올바르지 않습니다.",
                "details": serializer.errors
            }, status=400)

        title = serializer.validated_data['title']
        pdf_file = serializer.validated_data['pdf']
        
        print(f"✅ 검증 완료 - 제목: {title}, 파일명: {pdf_file.name}")

        try:
            # 1. PDF 텍스트 추출
            print("📖 PDF 텍스트 추출 시작...")
            extracted_text = extract_text_from_pdf(pdf_file)
            print(f"📄 추출된 텍스트 길이: {len(extracted_text)} 문자")

            # 2. Gemini 요약
            print("🤖 Gemini API 요약 시작...")
            summary = summarize_with_gemini(extracted_text)
            print(f"📝 요약 완료: {len(summary)} 문자")

            # 3. S3 업로드 => pdf_URL을 얻어냄
            print("☁️ S3 업로드 시작...")
            pdf_file.seek(0)
            pdf_url = upload_to_s3(pdf_file)
            print(f"🔗 S3 업로드 완료: {pdf_url}")

            # 4. DB 저장 (user 외래키 없음)
            print("💾 DB 저장 시작...")
            book = Book.objects.create(
                title=title,
                content=summary,
                pdf_url=pdf_url
            )
            print(f"✅ 책 생성 완료 - ID: {book.id}")

            return Response({
                "book_id": book.id,
                "title": book.title,
                "content": book.content,
                "pdf_url": book.pdf_url
            }, status=201)

        except Exception as e:
            print(f"[ERROR] PDF 처리 중 오류 발생: {str(e)}")
            print(f"[ERROR] 오류 타입: {type(e).__name__}")
            import traceback
            print(f"[ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")
            
            return Response({
                "status": "error",
                "error_code": 500,
                "message": f"PDF 처리 중 오류가 발생했습니다: {str(e)}"
            }, status=500)


class BookOfficialView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="삭제되지 않은 모든 책 목록을 조회합니다. (JWT 인증 필요)",
        responses={
            200: BookOfficialResponseSerializer(many=True),
            401: openapi.Response(description="인증 필요"),
            500: BookErrorResponseSerializer
        },
        tags=['책 관리']
    )
    def get(self, request):
        # 삭제되지 않은 모든 책 조회 (사용자별 필터링 없음)
        books = Book.objects.filter(is_deleted=False).only('id', 'title', 'content')
        
        print(f"📚 인증된 사용자 {request.user.username}이 책 {books.count()}개 조회")
        
        # 응답 데이터 직렬화
        response_serializer = BookOfficialResponseSerializer(books, many=True)
        
        # 성공 응답 반환
        return Response(response_serializer.data, status=status.HTTP_200_OK)

class BookVideosView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="특정 책의 모든 캐릭터들의 비디오 목록을 조회합니다. (JWT 인증 필요)",
        responses={
            200: BookVideoResponseSerializer(many=True),
            401: openapi.Response(description="인증 필요"),
            404: openapi.Response(
                description="책을 찾을 수 없음",
                examples={"application/json": {
                    "status": "error",
                    "error_code": 404,
                    "message": "책을 찾을 수 없습니다."
                }}
            ),
            500: BookErrorResponseSerializer
        },
        tags=['책 관리']
    )
    def get(self, request, book_id):
        try:
            # 책 존재 여부 확인 (사용자별 필터링 없음)
            book = Book.objects.get(id=book_id, is_deleted=False)
            
            print(f"📚 인증된 사용자 {request.user.username}이 책 '{book.title}' 비디오 조회")
            
            # 해당 책의 캐릭터들 조회
            characters = book.characters.filter(is_deleted=False)

            # 캐릭터들의 비디오들 조회
            videos = Video.objects.filter(character__in=characters)

            # 응답 데이터 직렬화
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
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="특정 책의 모든 캐릭터 목록을 조회합니다. (JWT 인증 필요)",
        responses={
            200: BookCharacterResponseSerializer(many=True),
            401: openapi.Response(description="인증 필요"),
            404: openapi.Response(
                description="책을 찾을 수 없음",
                examples={"application/json": {
                    "status": "error",
                    "error_code": 404,
                    "message": "책을 찾을 수 없습니다."
                }}
            ),
            500: BookErrorResponseSerializer
        },
        tags=['책 관리']
    )
    def get(self, request, book_id): 
        try:
            # 책 존재 여부 확인 (사용자별 필터링 없음)
            book = Book.objects.get(id=book_id, is_deleted=False)
            
            print(f"📚 인증된 사용자 {request.user.username}이 책 '{book.title}' 캐릭터 조회")
            
            # 해당 책의 캐릭터들 조회
            characters = book.characters.filter(is_deleted=False)

            # 응답 데이터 직렬화
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
