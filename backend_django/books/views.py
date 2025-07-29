"""Books 앱 views.py"""

import logging
import asyncio
import threading
from datetime import datetime
from django.utils import timezone
from django.core.cache import caches
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated  # JWT 인증 추가
from books.pdf_utils import extract_text_from_pdf # pdf 파일에서 텍스트를 추출하는 함수
from books.gemini_client import summarize_with_gemini # Gemini를 이용한 pdf 책 요약 함수
from books.s3_client import upload_to_s3 # S3에 파일을 업로드하는 함수
from .serializers import (
    BookPdfUploadSerializer,
    BookOfficialResponseSerializer,
    BookVideoResponseSerializer,
    BookCharacterResponseSerializer,
    BookErrorResponseSerializer,
    BookSuccessResponseSerializer,
    BookAsyncUploadResponseSerializer,
)
from .tasks import process_book_pdf_task

from .models import Book
from veo3Video.models import Video
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
# Create your views here.

from .models import Book
from .serializers import BookPdfUploadSerializer
from characters.models import Character
from .tasks import process_book_pdf_task
from rest_framework.permissions import IsAuthenticated


'''SSE 스트리밍 연결을 위한 뷰 함수 - 클라이언트에게 이벤트 메시지 전송용'''
def task_eventstream_view(request, task_id):
    """
    직접 구현한 SSE 스트리밍 뷰
    """
    def event_generator():
        import redis
        import json
        import time
        
        # Redis 연결
        redis_client = redis.Redis(host='backend-redis', port=6379, db=3, decode_responses=True)
        pubsub = redis_client.pubsub()
        
        # 채널 구독
        channel = f"task-{task_id}"
        pubsub.subscribe(channel)
        
        print(f"[SSE] 클라이언트 연결됨 - 채널: {channel}")
        
        try:
            # 연결 성공 메시지
            yield f"event: connected\n"
            yield f"data: {json.dumps({'message': 'SSE 연결 성공', 'channel': channel})}\n\n"
            
            # Redis pub/sub 메시지 대기
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        event_type = data.get('event', 'message')
                        event_data = data.get('data', {})
                        
                        yield f"event: {event_type}\n"
                        yield f"data: {json.dumps(event_data)}\n\n"
                        
                        # completed 이벤트면 연결 종료
                        if event_type == 'completed':
                            break
                            
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"[SSE] 메시지 파싱 오류: {e}")
                        
        except Exception as e:
            print(f"[SSE] 연결 오류: {e}")
        finally:
            pubsub.close()
            print(f"[SSE] 연결 종료 - 채널: {channel}")
    
    from django.http import StreamingHttpResponse
    response = StreamingHttpResponse(event_generator(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Cache-Control'
    return response


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
            
            # 3. Celery 태스크 시작 - Celery 호출 함수를 이용하여 작업을 명령
            task = process_book_pdf_task.delay(
                book_id=book.id,
                pdf_file_content=pdf_base64,
                pdf_file_name=pdf_file.name
            )
            
            # 즉시 테스트 이벤트 전송 (Redis 직접 발행)
            try:
                import redis
                import json
                
                redis_client = redis.Redis(host='backend-redis', port=6379, db=3)
                redis_ping = redis_client.ping()
                print(f"[TEST] Redis 연결 테스트: {redis_ping}")
                
                test_message = {
                    "event": "test",
                    "data": {
                        "message": "즉시 전송되는 테스트 이벤트",
                        "task_id": task.id,
                        "timestamp": str(timezone.now())
                    }
                }
                
                channel = f"task-{task.id}"
                redis_client.publish(channel, json.dumps(test_message))
                print(f"[TEST] Redis 테스트 이벤트 전송 성공 - 채널: {channel}")
                
            except Exception as e:
                print(f"[TEST] Redis 테스트 이벤트 전송 실패 - 오류: {str(e)}")
                import traceback
                print(f"[TEST] 상세 오류: {traceback.format_exc()}")
            
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
                "message": "PDF 처리가 시작되었습니다. 실시간 처리 상태는 EventStream을 통해 확인 가능합니다: GET /books/{book_id}/eventstream/processing"
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



# 책 입력 API 2가지를 정의함
# ''' 책 텍스트로 입력시 book을 생성하는 API '''
# class BookTextUploadView(APIView):
#     permission_classes = [IsAuthenticated]  # JWT 인증 필요

#     @swagger_auto_schema(
#         operation_description="텍스트로 책을 생성합니다. (JWT 인증 필요)",
#         request_body=BookCreateSerializer,
#         responses={
#             201: BookSuccessResponseSerializer,
#             400: BookErrorResponseSerializer,
#             401: openapi.Response(description="인증 필요")
#         },
#         tags=['책 관리']
#     )
#     def post(self, request):
#         serializer = BookCreateSerializer(data=request.data)
#         if serializer.is_valid():
#             # 책 생성 (user 외래키 없음)
#             book = serializer.save()
#             return Response({
#                 "book_id": book.id,
#                 "title": book.title,
#                 "content": book.content,
#                 "book_url": None
#             }, status=status.HTTP_201_CREATED)
#         return Response({
#             "status": "error",
#             "error_code": 400,
#             "message": "입력한 정보 형식이 올바르지 않습니다.",
#             "details": serializer.errors
#         }, status=status.HTTP_400_BAD_REQUEST)
    