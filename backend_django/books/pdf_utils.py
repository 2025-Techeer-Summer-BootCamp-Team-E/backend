# books/utils/pdf_utils.py

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes
import logging

logger = logging.getLogger(__name__)

''' PDF 파일에서 텍스트를 추출하는 함수 '''
def extract_text_from_pdf(file) -> str:
    try:
        file.seek(0)
        pdf_data = file.read()
        
        # PDF 파일 열기 시도
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
        except TypeError as e:
            if "Pipeline" in str(e):
                logger.error(f"PyMuPDF Pipeline 오류 - 라이브러리 버전 문제일 수 있음: {e}")
                raise ValueError(f"PDF 처리 라이브러리 오류입니다. 관리자에게 문의하세요.")
            else:
                logger.error(f"PDF 파일 열기 실패 (타입 오류): {e}")
                raise ValueError(f"유효하지 않은 PDF 파일입니다: {e}")
        except Exception as e:
            logger.error(f"PDF 파일 열기 실패: {e}")
            raise ValueError(f"유효하지 않은 PDF 파일입니다: {e}")
        
        text = ""
        try:
            # 텍스트 기반 추출 시도
            for page in doc:
                try:
                    page_text = page.get_text()
                    text += page_text
                except Exception as e:
                    logger.warning(f"페이지 {page.number} 텍스트 추출 실패: {e}")
                    continue
        except Exception as e:
            logger.error(f"PDF 텍스트 추출 중 오류: {e}")
        finally:
            doc.close()
        
        if text.strip():
            return text.strip()  # ✅ 텍스트 기반 PDF

        # OCR 처리 시도 (이미지 기반 PDF)
        try:
            file.seek(0)
            images = convert_from_bytes(pdf_data)
            ocr_text = ""
            
            for i, image in enumerate(images):
                try:
                    page_ocr = pytesseract.image_to_string(image, lang='eng+kor')
                    ocr_text += page_ocr
                except Exception as e:
                    logger.warning(f"페이지 {i+1} OCR 처리 실패: {e}")
                    continue
            
            return ocr_text.strip()
            
        except Exception as e:
            logger.error(f"OCR 처리 중 오류: {e}")
            raise ValueError(f"PDF를 이미지로 변환하거나 OCR 처리 중 오류가 발생했습니다: {e}")
    
    except ValueError:
        # 이미 처리된 ValueError는 다시 발생
        raise
    except Exception as e:
        logger.error(f"PDF 텍스트 추출 중 예상치 못한 오류: {e}")
        raise RuntimeError(f"PDF 처리 중 예상치 못한 오류가 발생했습니다: {e}")
