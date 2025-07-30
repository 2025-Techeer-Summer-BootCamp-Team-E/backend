from django.test import TestCase, TransactionTestCase
from unittest.mock import patch, MagicMock
from veo3Video.tasks import create_video_for_scene, combine_videos_task
from veo3Video.models import Video
from characters.models import Character
from django.contrib.auth import get_user_model
from books.models import Book # Book 모델 임포트
import json
import os

class VideoTaskTest(TestCase):
    def setUp(self):
        # 테스트용 사용자 생성
        User = get_user_model()
        self.test_user = User.objects.create_user(username='testuser', password='testpassword')

        # 테스트용 책 생성 (Character 모델이 Book을 참조하므로 필요)
        self.test_book = Book.objects.create(title="Test Book", content="Some content")

        # 테스트용 캐릭터 생성
        self.test_character = Character.objects.create(
            characterName="Test Character",
            isMain=True,
            age=30,
            gender="Male",
            characterDescription="A test character.",
            book=self.test_book # Book 인스턴스 연결
        )
        self.channel_id = "test-channel-123"

    @patch('veo3Video.tasks.generate_video_from_text')
    @patch('veo3Video.tasks.generate_signed_url')
    @patch('veo3Video.tasks.redis_client.publish')
    def test_create_video_for_scene_with_user_id(self, mock_publish, mock_generate_signed_url, mock_generate_video_from_text):
        # Mocking generate_video_from_text
        mock_generate_video_from_text.return_value = {
            "video_uri": "gs://mock-bucket/mock-video.mp4"
        }
        # Mocking generate_signed_url
        mock_generate_signed_url.return_value = "https://mock-signed-url.com/mock-video.mp4"

        # create_video_for_scene 태스크 호출
        create_video_for_scene(
            character_id=self.test_character.id,
            prompt="Test prompt",
            title="Test Title",
            channel_id=self.channel_id,
            user_id=self.test_user.id
        )

        # Video 객체가 생성되었는지 확인
        self.assertEqual(Video.objects.count(), 1)
        video = Video.objects.first()
        self.assertEqual(video.title, "Test Title")
        self.assertEqual(video.user, self.test_user) # user_id가 올바르게 저장되었는지 확인
        self.assertEqual(video.character, self.test_character)

        # Redis publish가 호출되었는지 확인
        mock_publish.assert_called()
        # 첫 번째 publish 호출의 메시지 확인 (예시)
        # args, kwargs = mock_publish.call_args
        # self.assertEqual(args[0], self.channel_id)
        # message_data = json.loads(args[1])
        # self.assertEqual(message_data['status'], 'scene_creation_started')


    @patch('veo3Video.tasks.subprocess.run')
    @patch('veo3Video.tasks.storage.Client')
    @patch('veo3Video.tasks.generate_signed_url')
    @patch('veo3Video.tasks.redis_client.publish')
    @patch('veo3Video.tasks.tempfile.NamedTemporaryFile')
    def test_combine_videos_task_with_thumbnail(self, mock_tempfile, mock_publish, mock_generate_signed_url, mock_storage_client, mock_subprocess_run):
        # Mocking GCS client and blob operations
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_blob.exists.return_value = False # 썸네일 이름 중복 방지 로직 테스트를 위해 False로 설정

        # Mocking subprocess.run for ffmpeg
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        # Mocking tempfile.NamedTemporaryFile
        mock_tempfile_video = MagicMock(name='video_file')
        mock_tempfile_video.name = '/tmp/mock_combined_video.mp4'
        mock_tempfile_video.close.return_value = None

        mock_tempfile_txt = MagicMock(name='txt_file')
        mock_tempfile_txt.name = '/tmp/mock_input_list.txt'
        mock_tempfile_txt.close.return_value = None
        mock_tempfile_txt.write.return_value = None

        mock_tempfile_thumbnail = MagicMock(name='thumbnail_file')
        mock_tempfile_thumbnail.name = '/tmp/mock_thumbnail.jpg'
        mock_tempfile_thumbnail.close.return_value = None

        # NamedTemporaryFile 호출 순서에 따라 Mock 객체 반환
        mock_tempfile.side_effect = [
            MagicMock(close=MagicMock(), name='/tmp/temp_file_0.mp4'),
            MagicMock(close=MagicMock(), name='/tmp/temp_file_1.mp4'),
            MagicMock(close=MagicMock(), name='/tmp/temp_file_2.mp4'),
            mock_tempfile_txt,
            mock_tempfile_video,
            mock_tempfile_thumbnail
        ]
