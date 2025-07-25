from celery import shared_task
import tempfile
import os
from django.core.files.base import ContentFile
from .models import Book
from .pdf_utils import extract_text_from_pdf
from .gemini_client import summarize_with_gemini
from .s3_client import upload_to_s3

@shared_task(bind=True)
def process_book_pdf_task(self, book_id, pdf_file_content, pdf_file_name):
    """
    PDF 파일을 비동기적으로 처리하는 Celery 태스크
    
    Args:
        book_id: Book 인스턴스 ID
        pdf_file_content: PDF 파일 바이너리 내용 (base64 인코딩된 문자열)
        pdf_file_name: PDF 파일명
    """
    try:
        # Book 인스턴스 조회
        book = Book.objects.get(id=book_id)
        book.processing_status = 'PROCESSING'
        book.task_id = self.request.id
        book.save()
        
        print(f"📚 책 PDF 처리 시작 - ID: {book_id}, 제목: {book.title}")
        
        # base64 디코딩하여 임시 파일 생성
        import base64
        pdf_binary = base64.b64decode(pdf_file_content)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_binary)
            temp_file_path = temp_file.name
        
        try:
            # 1. PDF 텍스트 추출
            print("📖 PDF 텍스트 추출 시작...")
            # Django의 ContentFile로 변환하여 기존 함수 재사용
            with open(temp_file_path, 'rb') as f:
                pdf_file = ContentFile(f.read(), name=pdf_file_name)
            
            extracted_text = extract_text_from_pdf(pdf_file)
            print(f"📄 추출된 텍스트 길이: {len(extracted_text)} 문자")
            
            # 2. Gemini 요약
            print("🤖 Gemini API 요약 시작...")
            summary = summarize_with_gemini(extracted_text)
            print(f"📝 요약 완료: {len(summary)} 문자")
            
            # 3. S3 업로드
            print("☁️ S3 업로드 시작...")
            pdf_file.seek(0)  # 파일 포인터 초기화
            pdf_url = upload_to_s3(pdf_file)
            print(f"🔗 S3 업로드 완료: {pdf_url}")
            
            # 4. DB 업데이트
            book.content = summary
            book.pdf_url = pdf_url
            book.processing_status = 'COMPLETED'
            book.error_message = None
            book.save()
            
            print(f"✅ 책 PDF 처리 완료 - ID: {book_id}")
            
            return {
                "status": "success",
                "book_id": book_id,
                "title": book.title,
                "pdf_url": pdf_url,
                "content_length": len(summary)
            }
            
        finally:
            # 임시 파일 정리
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print(f"🗑️ 임시 파일 정리 완료: {temp_file_path}")
    
    except Book.DoesNotExist:
        error_msg = f"책을 찾을 수 없습니다 - ID: {book_id}"
        print(f"❌ {error_msg}")
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
        
        import traceback
        print(f"❌ 상세 스택 트레이스:\n{traceback.format_exc()}")
        
        # Celery에 실패 상태 전달
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'book_id': book_id}
        )
        raise Exception(error_msg) 