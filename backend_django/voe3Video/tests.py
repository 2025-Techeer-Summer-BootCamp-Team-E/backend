from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock, ANY
from django.urls import reverse
from .models import Video
import json
import uuid

# Video 모델에 대한 테스트 클래스
# 이 클래스는 Video 모델의 데이터베이스 상호작용 및 속성들을 검증합니다.
class VideoModelTest(TestCase):
    # 테스트 케이스: 비디오 객체 생성
    # 목적: Video 모델 인스턴스가 올바르게 생성되고 데이터베이스에 저장되는지 확인합니다.
    def test_video_creation(self):
        # 수행 작업: Video 모델의 인스턴스를 생성하고 데이터베이스에 저장합니다.
        video = Video.objects.create(
            video_uri="gs://test_bucket/test_video_1.mp4",
            prompt="A test prompt for video 1.",
            title="Test Video Title 1",
            user_id="test_user_1"
        )

        # 예상 결과:
        # 1. 생성된 비디오 객체의 'video_uri' 속성이 예상한 값과 일치해야 합니다.
        self.assertEqual(video.video_uri, "gs://test_bucket/test_video_1.mp4")
        # 2. 생성된 비디오 객체의 'title' 속성이 예상한 값과 일치해야 합니다.
        self.assertEqual(video.title, "Test Video Title 1")
        # 3. 'created_at' 필드가 자동으로 설정되었는지 (None이 아닌지) 확인합니다.
        self.assertIsNotNone(video.created_at)
        # 4. 데이터베이스에 정확히 하나의 Video 객체가 존재해야 합니다.
        self.assertEqual(Video.objects.count(), 1)

    # 테스트 케이스: 비디오 객체의 문자열 표현 확인
    # 목적: Video 모델의 __str__ 메서드가 올바른 문자열을 반환하는지 검증합니다.
    def test_video_str_representation(self):
        # 수행 작업: Video 모델의 인스턴스를 생성합니다.
        video = Video.objects.create(
            video_uri="gs://test_bucket/test_video_2.mp4",
            prompt="Another test prompt.",
            title="Test Video Title 2",
            user_id="test_user_2"
        )
        # 예상 결과: Video 객체의 __str__ 메서드가 '제목 (사용자ID)' 형식의 문자열을 반환해야 합니다.
        self.assertEqual(str(video), "Test Video Title 2 (test_user_2)")

# Video API 엔드포인트에 대한 테스트 클래스
# 이 클래스는 비디오 생성 및 목록 조회 API 엔드포인트의 동작을 검증합니다.
class VideoAPITest(TestCase):
    # 각 테스트 메서드 실행 전에 호출되는 설정 메서드
    def setUp(self):
        self.client = APIClient()
        self.generate_url = reverse('generate_video')
        self.list_url = reverse('list_videos')
        self.toggle_bookmark_url_name = 'toggle_bookmark'
        self.list_bookmarked_url = reverse('list_bookmarked_videos')

    # 테스트 케이스: 비디오 생성 API 성공 시나리오
    # 목적: 유효한 데이터로 비디오 생성 API를 호출했을 때, 성공적으로 비디오가 생성되고 데이터베이스에 저장되며, 올바른 응답을 반환하는지 확인합니다.
    # @patch 데코레이터를 사용하여 veo_service.py의 외부 API 호출 함수들을 모킹합니다.
    # 이렇게 하면 실제 Google Cloud API 호출 없이 테스트를 빠르게 실행하고 비용을 절감할 수 있습니다.
    @patch('voe3Video.veo_service.storage.Client')
    @patch('voe3Video.veo_service.client.models.generate_videos')
    @patch('voe3Video.veo_service.generate_signed_url')
    def test_generate_video_api_success(self, mock_generate_signed_url, mock_generate_videos, mock_storage_client):
        # 1. GCS 클라이언트 및 관련 객체들을 모킹합니다.
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.copy_blob.return_value = MagicMock() # copy_blob이 새로운 blob 객체를 반환하도록 설정

        # 2. `generate_videos` 함수가 반환할 가짜 `operation` 객체를 설정합니다.
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_operation.response = MagicMock()
        mock_operation.result = MagicMock()
        mock_operation.result.generated_videos = [MagicMock()]
        # 임시 파일 경로를 모킹합니다.
        temp_video_uri = f"gs://mock_bucket/{uuid.uuid4()}/sample_0.mp4"
        mock_operation.result.generated_videos[0].video.uri = temp_video_uri
        mock_generate_videos.return_value = mock_operation

        # 3. `generate_signed_url` 함수가 반환할 가짜 서명된 URL을 설정합니다.
        mock_generate_signed_url.return_value = "http://mock_signed_url_1.com"

        # 4. 비디오 생성 API에 POST 요청을 보낼 데이터를 준비합니다.
        data = {
            "prompt": "A test prompt for API.",
            "title": "API Test Video"
        }
        # 5. API에 POST 요청을 보냅니다.
        response = self.client.post(self.generate_url, data, format='json')

        # 예상 결과:
        self.assertEqual(response.status_code, 200)
        self.assertIn("video_uri", response.data)
        # 최종 video_uri가 예상대로 'generated_videos/' 폴더에 있는지 확인합니다.
        self.assertTrue(response.data['video_uri'].startswith('gs://mock_bucket/generated_videos/video_'))
        self.assertIn("signed_url", response.data)
        self.assertEqual(Video.objects.count(), 1)

        # GCS 복사 및 삭제 작업이 호출되었는지 확인합니다.
        mock_bucket.copy_blob.assert_called_once()
        mock_blob.delete.assert_called_once()

    # 테스트 케이스: 비디오 생성 API 필수 필드 누락 시나리오
    # 목적: 필수 필드(prompt, title) 중 하나라도 누락되었을 때, API가 400 Bad Request를 반환하고
    #      비디오 생성 로직이 호출되지 않는지 확인합니다.
    @patch('voe3Video.veo_service.client.models.generate_videos')
    def test_generate_video_api_missing_fields(self, mock_generate_videos):
        # 수행 작업:
        # 1. 필수 필드(title)가 누락된 데이터를 준비합니다.
        data = {"prompt": "Only prompt"}
        # 2. API에 POST 요청을 보냅니다.
        response = self.client.post(self.generate_url, data, format='json')

        # 예상 결과:
        # 1. 응답 상태 코드가 400 (Bad Request)이어야 합니다.
        self.assertEqual(response.status_code, 400)
        # 2. 응답 데이터에 'error' 필드가 포함되어야 합니다.
        self.assertIn("error", response.data)
        # 3. 데이터베이스에 Video 객체가 저장되지 않아야 합니다.
        self.assertEqual(Video.objects.count(), 0)
        # 4. `mock_generate_videos` 함수가 호출되지 않아야 합니다.
        mock_generate_videos.assert_not_called()

    # 테스트 케이스: 비디오 목록 조회 API 성공 시나리오
    # 목적: 데이터베이스에 비디오가 존재할 때, 비디오 목록 조회 API가 올바른 데이터를 반환하는지 확인합니다.
    def test_list_videos_api_success(self):
        # 수행 작업:
        # 1. 테스트용 Video 객체 두 개를 데이터베이스에 직접 생성합니다.
        #    이 객체들은 테스트 데이터베이스에 저장되며, 테스트 종료 시 자동으로 삭제됩니다.
        Video.objects.create(
            video_uri="gs://test_bucket/list_video_1.mp4",
            prompt="List test 1",
            title="List Video 1",
            user_id="user1"
        )
        Video.objects.create(
            video_uri="gs://test_bucket/list_video_2.mp4",
            prompt="List test 2",
            title="List Video 2",
            user_id="user2"
        )

        # 2. `generate_signed_url` 함수를 모킹하여 실제 GCS 호출을 방지하고 가짜 URL을 반환하도록 설정합니다.
        #    `side_effect`를 사용하여 `generate_signed_url`이 호출될 때마다 동적으로 가짜 URL을 생성합니다.
        with patch('voe3Video.veo_service.generate_signed_url') as mock_generate_signed_url:
            # 람다 함수는 `generate_signed_url`이 받는 인자(uri)를 받아 가짜 서명된 URL을 생성합니다.
            mock_generate_signed_url.side_effect = lambda uri: f"http://mock_signed_url_for_{uri.split('/')[-1]}"
            # 3. 비디오 목록 조회 API에 GET 요청을 보냅니다.
            response = self.client.get(self.list_url)

        # 예상 결과:
        # 1. 응답 상태 코드가 200 (OK)이어야 합니다.
        self.assertEqual(response.status_code, 200)
        # 2. 응답 데이터의 길이가 2 (생성된 비디오 수)이어야 합니다.
        self.assertEqual(len(response.data), 2)
        # 3. 응답 데이터의 첫 번째 항목에 'video_uri' 필드가 포함되어야 합니다.
        self.assertIn("video_uri", response.data[0])
        # 4. 응답 데이터의 첫 번째 항목에 'signed_url' 필드가 포함되어야 합니다.
        self.assertIn("signed_url", response.data[0])
        # 5. 응답 데이터의 첫 번째 항목에 'prompt' 필드가 포함되어야 합니다.
        self.assertIn("prompt", response.data[0])
        # 6. 응답 데이터의 첫 번째 항목에 'created_at' 필드가 포함되어야 합니다.
        self.assertIn("created_at", response.data[0])
        # 7. 비디오 목록이 'created_at' 필드를 기준으로 최신순으로 정렬되어 반환되는지 확인합니다.
        self.assertEqual(response.data[0]['title'], "List Video 2")
        self.assertEqual(response.data[1]['title'], "List Video 1")

    # 테스트 케이스: 비디오 목록 조회 API (빈 목록 시나리오)
    # 목적: 데이터베이스에 비디오가 존재하지 않을 때, 비디오 목록 조회 API가 빈 목록을 올바르게 반환하는지 확인합니다.
    def test_list_videos_api_empty(self):
        # 수행 작업:
        # 1. 데이터베이스에 아무런 Video 객체도 생성하지 않은 상태에서
        # 2. 비디오 목록 조회 API에 GET 요청을 보냅니다.
        response = self.client.get(self.list_url)

        # 예상 결과:
        # 1. 응답 상태 코드가 200 (OK)이어야 합니다.
        # 2. 응답 데이터의 길이가 0 (빈 목록)이어야 합니다.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    # 테스트 케이스: 북마크 토글 API 성공 시나리오
    # 목적: 비디오의 북마크 상태를 성공적으로 토글하는지 확인합니다.
    def test_toggle_bookmark_api_success(self):
        # 1. 테스트용 비디오 생성 (초기 is_bookmarked는 False)
        video = Video.objects.create(
            video_uri="gs://test_bucket/toggle_video.mp4",
            prompt="Toggle test",
            title="Toggle Video",
            user_id="user_toggle"
        )
        self.assertFalse(video.is_bookmarked) # 초기 상태 확인

        # 2. 북마크 토글 API 호출 (PATCH 요청)
        response = self.client.patch(reverse(self.toggle_bookmark_url_name, args=[video.id]))

        # 3. 응답 확인
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_bookmarked']) # 응답에서 is_bookmarked가 True인지 확인

        # 4. 데이터베이스에서 비디오 객체를 다시 로드하여 상태 확인
        video.refresh_from_db()
        self.assertTrue(video.is_bookmarked) # 데이터베이스에서 is_bookmarked가 True인지 확인

        # 5. 다시 토글하여 False로 변경
        response = self.client.patch(reverse(self.toggle_bookmark_url_name, args=[video.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_bookmarked']) # 응답에서 is_bookmarked가 False인지 확인

        video.refresh_from_db()
        self.assertFalse(video.is_bookmarked) # 데이터베이스에서 is_bookmarked가 False인지 확인

    # 테스트 케이스: 북마크 토글 API - 존재하지 않는 비디오
    # 목적: 존재하지 않는 비디오 ID로 북마크 토글을 시도했을 때 404 응답을 반환하는지 확인합니다.
    def test_toggle_bookmark_api_not_found(self):
        # 존재하지 않는 비디오 ID로 요청
        non_existent_id = 99999
        response = self.client.patch(reverse(self.toggle_bookmark_url_name, args=[non_existent_id]))

        # 404 응답 확인
        self.assertEqual(response.status_code, 404)

    # 테스트 케이스: 북마크된 비디오 목록 조회 API 성공 시나리오
    # 목적: 북마크된 비디오만 올바르게 반환하는지 확인합니다.
    def test_list_bookmarked_videos_api_success(self):
        # 1. 테스트용 비디오 생성 (일부는 북마크, 일부는 북마크 안 함)
        Video.objects.create(
            video_uri="gs://test_bucket/video_not_bookmarked.mp4",
            prompt="Not bookmarked",
            title="Video Not Bookmarked",
            is_bookmarked=False
        )
        bookmarked_video1 = Video.objects.create(
            video_uri="gs://test_bucket/video_bookmarked1.mp4",
            prompt="Bookmarked 1",
            title="Video Bookmarked 1",
            is_bookmarked=True
        )
        bookmarked_video2 = Video.objects.create(
            video_uri="gs://test_bucket/video_bookmarked2.mp4",
            prompt="Bookmarked 2",
            title="Video Bookmarked 2",
            is_bookmarked=True
        )

        # 2. `generate_signed_url` 함수를 모킹하여 실제 GCS 호출 방지
        with patch('voe3Video.veo_service.generate_signed_url') as mock_generate_signed_url:
            mock_generate_signed_url.side_effect = lambda uri: f"http://mock_signed_url_for_{uri.split('/')[-1]}"
            # 3. 북마크된 비디오 목록 조회 API 호출
            response = self.client.get(self.list_bookmarked_url)

        # 4. 응답 확인
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2) # 북마크된 비디오는 2개여야 함

        # 반환된 비디오들이 올바른지 확인 (ID 또는 제목으로)
        returned_titles = {video['title'] for video in response.data}
        self.assertIn("Video Bookmarked 1", returned_titles)
        self.assertIn("Video Bookmarked 2", returned_titles)
        self.assertNotIn("Video Not Bookmarked", returned_titles)

    # 테스트 케이스: 북마크된 비디오 목록 조회 API (빈 목록 시나리오)
    # 목적: 북마크된 비디오가 없을 때 빈 목록을 올바르게 반환하는지 확인합니다.
    def test_list_bookmarked_videos_api_empty(self):
        # 데이터베이스에 비디오가 없거나, 모두 북마크되지 않은 상태
        Video.objects.create(
            video_uri="gs://test_bucket/video_not_bookmarked_empty.mp4",
            prompt="Not bookmarked empty",
            title="Video Not Bookmarked Empty",
            is_bookmarked=False
        )

        with patch('voe3Video.veo_service.generate_signed_url') as mock_generate_signed_url:
            mock_generate_signed_url.return_value = "http://mock_signed_url"
            response = self.client.get(self.list_bookmarked_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0) # 빈 목록이어야 함