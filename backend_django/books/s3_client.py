import boto3
import uuid
from django.conf import settings

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