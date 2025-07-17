FROM python:3.10

ENV PYTHONUNBUFFERED 1

# 작업 디렉토리 설정
WORKDIR /backend

# 의존성 파일 먼저 복사 → 레이어 캐싱 최적화
COPY ./requirements.txt .

# MySQL 클라이언트 및 빌드 도구 설치
# poppler-utils: PDF 파일에서 텍스트 추출을 위한 도구
# tesseract-ocr, kor, eng: OCR(광학 문자 인식) 도구, korean, english 언어 지원
# libleptonica-dev: Tesseract의 의존성 라이브러리
RUN apt-get update && \
    apt-get install -y \
    default-mysql-client \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    tesseract-ocr-kor \
    tesseract-ocr-eng

# uv를 사용하여 의존성 설치
RUN pip install uv && uv pip install --system --no-cache-dir -r requirements.txt


# 소스 코드 복사
COPY . .
COPY .env .env

# # collectstatic (이미 코드가 복사된 이후여야 함!)
# RUN python -c "import dotenv; dotenv.load_dotenv(); import os; print(os.environ.get('SECRET_KEY'))" && python manage.py collectstatic --noinput

# 기본 실행 명령
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
