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
    BookSuccessResponseSerializer,
    BookAsyncUploadResponseSerializer,
    BookStatusResponseSerializer
)
from .models import Book
from veo3Video.models import Video
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
    


''' 책 PDF 업로드 API (동기) '''
class BookFromPdfView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]  # JWT 인증 필요

    @swagger_auto_schema(
        operation_description="""PDF 파일을 업로드하여 책을 즉시 생성합니다. (JWT 인증 필요)
        
        처리 과정 (동기):
        1. PDF에서 텍스트 추출 (텍스트 기반 또는 OCR)
        2. Gemini API로 내용 요약
        3. S3에 PDF 파일 업로드
        4. DB에 최종 정보 저장 후 완성된 책 정보 반환
        
        가능한 오류:
        - 400: PDF 파일 누락, 잘못된 형식
        - 401: 인증 필요
        - 500: PDF 처리, Gemini API, S3 업로드 실패
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
        tags=['책 관리'],
        consumes=['multipart/form-data']
    )
    def post(self, request):
        print("📝 동기 PDF 업로드 요청 시작")
        print("👤 요청 사용자:", request.user.username if request.user.is_authenticated else "익명")

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
            # 1. Book 레코드 생성 (PROCESSING 상태)
            book = Book.objects.create(
                title=title,
                processing_status='PROCESSING'
            )
            print(f"📚 책 레코드 생성 완료 - ID: {book.id}")

            # 2. PDF에서 텍스트 추출
            print("📄 PDF 텍스트 추출 시작...")
            extracted_text = extract_text_from_pdf(pdf_file)
            print(f"✅ 텍스트 추출 완료 - 길이: {len(extracted_text)}자")

            # 3. Gemini API로 요약
            print("🤖 Gemini API 요약 시작...")
            summarized_content = summarize_with_gemini(extracted_text)
            print(f"✅ 요약 완료 - 길이: {len(summarized_content)}자")

            # 4. S3에 PDF 업로드
            print("☁️ S3 업로드 시작...")
            pdf_file.seek(0)  # 파일 포인터 리셋
            pdf_url = upload_to_s3(pdf_file, f"books/{book.id}")
            print(f"✅ S3 업로드 완료 - URL: {pdf_url}")

            # 5. 최종 Book 정보 업데이트 (COMPLETED 상태)
            book.content = summarized_content
            book.pdf_url = pdf_url
            book.processing_status = 'COMPLETED'
            book.save()
            
            print(f"🎉 책 생성 완료 - ID: {book.id}")

            # 6. 완성된 책 정보 반환
            return Response({
                "book_id": book.id,
                "title": book.title,
                "content": book.content,
                "pdf_url": book.pdf_url,
                "status": "생성 완료"
            }, status=201)  # 201 Created

        except Exception as e:
            print(f"[ERROR] PDF 처리 중 오류 발생: {str(e)}")
            print(f"[ERROR] 오류 타입: {type(e).__name__}")
            import traceback
            print(f"[ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")

            # 오류 발생 시 Book 상태 업데이트
            if 'book' in locals():
                book.processing_status = 'FAILED'
                book.error_message = str(e)
                book.save()

            return Response({
                "status": "error",
                "error_code": 500,
                "message": f"PDF 처리 중 오류가 발생했습니다: {str(e)}"
            }, status=500)


''' 책 PDF 업로드 API (비동기) '''
class BookFromPdfAsyncView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]  # JWT 인증 필요

    @swagger_auto_schema(
        operation_description="""PDF 파일을 업로드하여 책을 비동기적으로 생성합니다. (JWT 인증 필요)
        
        처리 과정:
        1. 즉시 책 레코드 생성 및 응답 반환
        2. 백그라운드에서 PDF 처리:
           - PDF에서 텍스트 추출 (텍스트 기반 또는 OCR)
           - Gemini API로 내용 요약
           - S3에 PDF 파일 업로드
           - DB에 최종 정보 업데이트
        
        가능한 오류:
        - 400: PDF 파일 누락, 잘못된 형식
        - 401: 인증 필요
        - 500: 초기 처리 실패
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
            202: BookAsyncUploadResponseSerializer,
            400: BookErrorResponseSerializer,
            401: openapi.Response(description="인증 필요"),
            500: BookErrorResponseSerializer
        },
        tags=['책 관리'],
        consumes=['multipart/form-data']
    )
    def post(self, request):
        print("📝 비동기 PDF 업로드 요청 시작")
        print("👤 요청 사용자:", request.user.username if request.user.is_authenticated else "익명")

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
            # 1. 즉시 Book 레코드 생성 (PENDING 상태)
            book = Book.objects.create(
                title=title,
                processing_status='PENDING'
            )
            print(f"📚 책 레코드 생성 완료 - ID: {book.id}")

            # 2. PDF 파일을 base64로 인코딩
            pdf_file.seek(0)
            pdf_content = pdf_file.read()
            import base64
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # 3. Celery 태스크 시작
            from .tasks import process_book_pdf_task
            task = process_book_pdf_task.delay(
                book_id=book.id,
                pdf_file_content=pdf_base64,
                pdf_file_name=pdf_file.name
            )
            
            # 4. 태스크 ID 저장
            book.task_id = task.id
            book.save()
            
            print(f"🚀 비동기 처리 시작 - Task ID: {task.id}")

            # 5. 즉시 응답 반환
            return Response({
                "book_id": book.id,
                "title": book.title,
                "processing_status": book.processing_status,
                "task_id": task.id,
                "message": "PDF 처리가 시작되었습니다. 처리 상태는 GET /books/{book_id}/status 로 확인 가능합니다."
            }, status=202)  # 202 Accepted

        except Exception as e:
            print(f"[ERROR] 초기 처리 중 오류 발생: {str(e)}")
            print(f"[ERROR] 오류 타입: {type(e).__name__}")
            import traceback
            print(f"[ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")

            return Response({
                "status": "error",
                "error_code": 500,
                "message": f"초기 처리 중 오류가 발생했습니다: {str(e)}"
            }, status=500)


''' 공용책 정보 API '''
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
        
        # print(f"📚 인증된 사용자 {request.user.username}이 책 {books.count()}개 조회")

        # 응답 데이터 직렬화
        response_serializer = BookOfficialResponseSerializer(books, many=True)
        
        # 성공 응답 반환
        return Response(response_serializer.data, status=status.HTTP_200_OK)


''' 책 동영상 API '''
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
            
            # print(f"📚 인증된 사용자 {request.user.username}이 책 '{book.title}' 비디오 조회")

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


''' 책 등장인물 목록 조회 API '''
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

            # print(f"📚 인증된 사용자 {request.user.username}이 책 '{book.title}' 캐릭터 조회")

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


''' 책 처리 상태 확인 API '''
class BookStatusView(APIView):
    """
    책 PDF 처리 상태를 확인하는 API
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="""책 PDF 처리 상태를 확인합니다. (JWT 인증 필요)
        
        처리 상태:
        - PENDING: 처리 대기 중
        - PROCESSING: 처리 진행 중  
        - COMPLETED: 처리 완료
        - FAILED: 처리 실패
        """,
        responses={
            200: BookStatusResponseSerializer,
            404: BookErrorResponseSerializer,
            401: openapi.Response(description="인증 필요")
        },
        tags=['책 관리']
    )
    def get(self, request, book_id):
        try:
            book = Book.objects.get(id=book_id, is_deleted=False)
            
            response_data = {
                "book_id": book.id,
                "title": book.title,
                "processing_status": book.processing_status,
                "task_id": book.task_id,
                "content": book.content,
                "pdf_url": book.pdf_url,
                "error_message": book.error_message,
                "created_at": book.created_at,
                "updated_at": book.updated_at
            }
            
            print(f"📊 책 상태 조회 - ID: {book_id}, 상태: {book.processing_status}")
            return Response(response_data, status=200)
            
        except Book.DoesNotExist:
            return Response({
                "status": "error",
                "error_code": 404,
                "message": "책을 찾을 수 없습니다."
            }, status=404)
