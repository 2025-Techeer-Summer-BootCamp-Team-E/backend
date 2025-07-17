import os
from django.core.management.base import BaseCommand
from google.cloud import storage
from django.conf import settings
from voe3Video.models import Video

class Command(BaseCommand):
    help = 'Imports video metadata from Google Cloud Storage into the Django database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting GCS video import...'))

        # GCS 클라이언트 초기화
        try:
            # settings.py에 GOOGLE_APPLICATION_CREDENTIALS 경로가 설정되어 있어야 합니다.
            # 또는 환경 변수 GOOGLE_APPLICATION_CREDENTIALS가 설정되어 있어야 합니다.
            storage_client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT_ID)
            bucket_name = settings.GOOGLE_CLOUD_GCS_BUCKET.replace('gs://', '').rstrip('/')
            self.stdout.write(self.style.NOTICE(f'Attempting to access GCS bucket: {bucket_name}'))
            bucket = storage_client.bucket(bucket_name)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to initialize GCS client or access bucket: {e}'))
            return

        # GCS 버킷에서 비디오 목록 조회
        try:
            blobs = bucket.list_blobs()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to list blobs in GCS bucket: {e}'))
            return

        imported_count = 0
        skipped_count = 0

        for blob in blobs:
            # mp4 파일만 처리 (필요에 따라 확장자 필터링)
            if not blob.name.endswith('.mp4'):
                self.stdout.write(self.style.NOTICE(f'Skipping non-mp4 file: {blob.name}'))
                continue

            video_uri = f'gs://{bucket_name}/{blob.name}'
            # 파일 이름에서 title 유추 (예: sample_0.mp4 -> sample_0)
            title = os.path.splitext(os.path.basename(blob.name))[0]
            prompt = f'Imported from GCS: {blob.name}' # 기본 프롬프트

            # 중복 확인
            if Video.objects.filter(video_uri=video_uri).exists():
                self.stdout.write(self.style.NOTICE(f'Skipping existing video: {video_uri}'))
                skipped_count += 1
                continue

            # Video 객체 생성 및 저장
            try:
                Video.objects.create(
                    video_uri=video_uri,
                    prompt=prompt,
                    title=title,
                    # user_id는 필요에 따라 설정하거나 None으로 둡니다.
                    user_id=None # 또는 특정 사용자 ID를 지정
                )
                self.stdout.write(self.style.SUCCESS(f'Successfully imported: {video_uri}'))
                imported_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to import {video_uri}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'GCS video import finished. Imported: {imported_count}, Skipped: {skipped_count}'
        ))
