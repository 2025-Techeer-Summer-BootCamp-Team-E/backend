import boto3
import uuid
from django.conf import settings
from urllib.parse import urlparse

# S3 클라이언트 설정
# aws s3 환경변수들을 이용해 s3에 업로드하는 클라이언트 정의
s3 = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME
)

def upload_to_s3(file_obj, folder='books') -> str:
    """
    PDF 파일을 S3에 업로드하고 public URL 반환
    """
    file_extension = file_obj.name.split('.')[-1]
    filename = f"{folder}/{uuid.uuid4()}.{file_extension}"

    s3.upload_fileobj(
        Fileobj=file_obj,
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=filename,
        ExtraArgs={'ContentType': 'application/pdf'}
    )

    url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{filename}"
    return url

def extract_s3_key_from_url(s3_url: str) -> str:
    """
    S3 URL에서 키(파일 경로)를 안전하게 추출
    
    Args:
        s3_url: S3 URL (예: https://bucket.s3.region.amazonaws.com/books/file.pdf)
    
    Returns:
        S3 키 (예: books/file.pdf)
    """
    if not s3_url:
        raise ValueError("S3 URL이 제공되지 않았습니다.")
    
    try:
        parsed = urlparse(s3_url)
        s3_key = parsed.path.lstrip('/')
        
        if not s3_key:
            raise ValueError("유효하지 않은 S3 URL 형식입니다.")
            
        return s3_key
    except Exception as e:
        raise ValueError(f"S3 URL 파싱 중 오류 발생: {str(e)}")

def generate_presigned_download_url(s3_key: str, expiration: int = 3600) -> str:
    """
    S3 파일에 대한 Presigned URL 생성 (다운로드용)
    
    Args:
        s3_key: S3 키 (파일 경로)
        expiration: URL 만료 시간 (초, 기본값: 1시간)
    
    Returns:
        Presigned URL
    """
    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expiration
        )
        return presigned_url
    except Exception as e:
        raise ValueError(f"Presigned URL 생성 중 오류 발생: {str(e)}")

def get_secure_pdf_url(s3_url: str, expiration: int = 3600) -> str:
    """
    저장된 S3 URL을 Presigned URL로 변환
    
    Args:
        s3_url: 데이터베이스에 저장된 S3 URL
        expiration: URL 만료 시간 (초, 기본값: 1시간)
    
    Returns:
        Presigned URL
    """
    s3_key = extract_s3_key_from_url(s3_url)
    return generate_presigned_download_url(s3_key, expiration)