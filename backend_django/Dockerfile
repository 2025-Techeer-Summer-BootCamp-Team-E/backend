# 1. 더 가벼운 베이스 이미지 사용
FROM python:3.10

ENV PYTHONUNBUFFERED 1

WORKDIR /backend

# 의존성 파일 복사
COPY ./requirements.txt .

# 시스템 패키지 설치 및 정리를 한 번에 수행
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-mysql-client \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    ffmpeg && \
    apt-get remove -y build-essential && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf ~/.cache/pip/*

# Python 패키지 설치
RUN pip install uv &&     uv pip install --system --no-cache-dir -r requirements.txt &&     python -c "import django_eventstream; print('django_eventstream installed successfully')" || exit 1 &&     rm -rf ~/.cache/pip/*

# 소스 코드 복사
COPY . .


# 기본 실행 명령 (환경변수에 따라 설정 파일 선택)
CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:8000"]