from celery import shared_task
import tempfile
import os
import base64
import traceback
import redis
import json
from django.core.files.base import ContentFile
from .models import Book
from .pdf_utils import extract_text_from_pdf
from .gemini_client import summarize_with_gemini
from .s3_client import upload_to_s3


'''SSE 알림을 직접 구현한 함수 - process_book_pdf_task()에서 호출하여 사용, Celery 태스크에서 직접 Redis를 통해 이벤트 전송'''
def send_task_event(task_id: str, event_type: str, data: dict):
    """
    Redis pub/sub을 통한 직접 이벤트 전송
    """
    try:
        # Redis 클라이언트 설정
        redis_client = redis.Redis(host='backend-redis', port=6379, db=3)
        # 채널 이름 설정, task - {task_id} 형태
        channel = f"task-{task_id}"
        # 이벤트 메시지 설정 
        message = {
            "event": event_type,
            "data": data
        }
        # 이벤트 메시지 전송
        redis_client.publish(channel, json.dumps(message))
        print(f"[DEBUG] Redis 이벤트 전송 성공 - 채널: {channel}, 타입: {event_type}")
        return True
        
    except Exception as e:
        print(f"[DEBUG] Redis 이벤트 전송 실패 - 채널: {channel}, 오류: {str(e)}")
        return False


''' Celery 태스크: 책 PDF 파일을 비동기적으로 처리하는 함수 '''
@shared_task(bind=True)
def process_book_pdf_task(self, book_id, pdf_file_content, pdf_file_name):
    """
    PDF 파일을 비동기적으로 처리하는 Celery 태스크
    
    Args:
        book_id: Book 인스턴스 ID
        pdf_file_content: PDF 파일 바이너리 내용 (base64 인코딩된 문자열)
        pdf_file_name: PDF 파일명
    """
    task_id = self.request.id
    temp_file_path = None

    print(f"[DEBUG] Celery 작업 시작됨 - book_id: {book_id}, task_id: {task_id}")

    try:
        # Book 인스턴스 조회
        book = Book.objects.get(id=book_id)
        book.processing_status = 'PROCESSING'
        book.task_id = task_id
        book.save()
        
        print(f"책 PDF 처리 시작 - ID: {book_id}, Task: {task_id}, 제목: {book.title}")
        print(f"[DEBUG] 채널명 예상: task-{task_id}")
        
        # 클라이언트 연결 시간 확보를 위한 지연 (5초) - 병렬 처리에서는 불필요하므로 주석 처리
        # print(f"[DEBUG] 클라이언트 연결 대기 중... (3초)")
        # import time
        # time.sleep(3)
        
        # 작업 시작 이벤트 전송 
        try:
            print(f"[DEBUG] started 이벤트 전송 시작 - 채널: task-{task_id}")
            # SSE 통신을 통해 이벤트 메시지 전송
            send_task_event(task_id, "started", {
                "message": "PDF 처리 시작됨", 
                "book_id": book_id,
                "book_title": book.title
            })
            print(f"[DEBUG] started 이벤트 전송 성공 - 채널: task-{task_id}")
        except Exception as e:
            print(f"[DEBUG] started 이벤트 전송 실패 - 채널: task-{task_id}, 오류: {str(e)}")
        
        # base64 디코딩하여 임시 파일 생성
        pdf_binary = base64.b64decode(pdf_file_content)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_binary)
            temp_file_path = temp_file.name

        # 1. PDF 텍스트 추출
        print("PDF 텍스트 추출 시작...")
        with open(temp_file_path, 'rb') as f:
            pdf_file = ContentFile(f.read(), name=pdf_file_name)
        
        extracted_text = extract_text_from_pdf(pdf_file)
        print(f"추출된 텍스트 길이: {len(extracted_text)} 문자")
        
        # 2. Gemini 요약
        print("Gemini API 요약 시작...")
        summary = summarize_with_gemini(extracted_text)
        print(f"요약 완료: {len(summary)} 문자")
        
        # 3. S3 업로드
        print("S3 업로드 시작...")
        pdf_file.seek(0)  # 파일 포인터 초기화
        pdf_url = upload_to_s3(pdf_file)
        print(f"S3 업로드 완료: {pdf_url}")
        
        # 4. DB 업데이트
        book.content = summary
        book.pdf_url = pdf_url
        book.processing_status = 'COMPLETED'
        book.error_message = None
        book.save()

        # 5. 완료 이벤트 전송 (S3 URL만 전송)
        try:
            # 작업 성공시 클라이언트에게 메시지 전송
            print(f"[DEBUG] completed 이벤트 전송 시작 - 채널: task-{task_id}")
            send_task_event(task_id, "completed", {"s3_url": pdf_url})
            print(f"[DEBUG] completed 이벤트 전송 성공 - 채널: task-{task_id}")
        except Exception as e:
            print(f"[DEBUG] completed 이벤트 전송 실패 - 채널: task-{task_id}, 오류: {str(e)}")
        
        print(f"✅ 책 PDF 처리 완료 - ID: {book_id}, Task: {task_id}")
        
        return {
            "status": "success",
            "book_id": book_id,
            "title": book.title,
            "pdf_url": pdf_url,
            "content_length": len(summary)
        }
        
    except Book.DoesNotExist:
        error_msg = f"책을 찾을 수 없습니다 - ID: {book_id}"
        print(f"❌ {error_msg}")
        try:
            # 오류 상태에 대한 로그 
            print(f"[DEBUG] error 이벤트 전송 시작 - 채널: task-{task_id}")
            send_task_event(task_id, "error", {"message": error_msg})
            print(f"[DEBUG] error 이벤트 전송 성공 - 채널: task-{task_id}")
        except Exception as e:
            print(f"[DEBUG] error 이벤트 전송 실패 - 채널: task-{task_id}, 오류: {str(e)}")
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"PDF 처리 중 오류 발생: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"❌ 오류 타입: {type(e).__name__}")
        
        # 오류 상태로 DB 업데이트
        try:
            book = Book.objects.get(id=book_id)
            book.processing_status = 'FAILED'
            book.error_message = error_msg
            book.save()
        except:
            pass
            
        # 오류 이벤트 전송
        try:
            print(f"[DEBUG] error 이벤트 전송 시작 - 채널: task-{task_id}")
            send_task_event(task_id, "error", {"message": error_msg})
            print(f"[DEBUG] error 이벤트 전송 성공 - 채널: task-{task_id}")
        except Exception as e:
            print(f"[DEBUG] error 이벤트 전송 실패 - 채널: task-{task_id}, 오류: {str(e)}")
        
        print(f"❌ 상세 스택 트레이스:\n{traceback.format_exc()}")
        
        # Celery에 실패 상태 전달
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'book_id': book_id}
        )
        raise Exception(error_msg)
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"🗑️ 임시 파일 정리 완료: {temp_file_path}") 