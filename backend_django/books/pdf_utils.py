# books/utils/pdf_utils.py

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes

def extract_text_from_pdf(file) -> str:
    file.seek(0)
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        page_text = page.get_text()
        text += page_text
    if text.strip():
        return text.strip()  # ✅ 텍스트 기반 PDF

    file.seek(0)
    images = convert_from_bytes(file.read())
    ocr_text = ""
    for image in images:
        ocr_text += pytesseract.image_to_string(image, lang='eng+kor')
    return ocr_text.strip()
