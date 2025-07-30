from django.db import models
from django.conf import settings

# 이 모델은 Google Cloud Storage(GCS)에 저장된 비디오의 메타데이터를 관리합니다.
# 각 필드는 비디오와 관련된 중요한 정보를 저장하며, 데이터베이스 스키마를 정의합니다.
class Video(models.Model):
    # video_uri: GCS에 저장된 비디오 파일의 URI (예: gs://your-bucket/path/to/video.mp4)
    # URLField를 사용하여 URL 형식의 문자열을 저장하며, 최대 길이 : 500자
    video_uri = models.TextField(verbose_name="GCS Video URI")
    
    # prompt: 비디오 생성에 사용된 텍스트 프롬프트
    # TextField를 사용하여 긴 텍스트를 저장, 최대 길이는 딱히 제한 없는것으로 보이나 2000자 이내로 암묵적으로 정했으면 함
    prompt = models.TextField(verbose_name="Video Generation Prompt")
    
    # title: 비디오의 제목
    # CharField를 사용하여 짧은 문자열을 저장하며, 최대 길이: 255자
    title = models.CharField(max_length=255, verbose_name="Video Title")
    
    # user: 비디오를 생성한 사용자 (User 모델과 외래키 관계)
    # ForeignKey를 사용하여 User 모델과 연결, null=True, blank=True로 설정하여 필수가 아니어도 괜찮도록 함
    # on_delete=models.CASCADE: 사용자가 삭제되면 해당 사용자의 비디오도 삭제
    # related_name='videos': User 모델에서 역참조할 때 사용할 이름 (user.videos.all())
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='videos', null=True, blank=True, verbose_name="생성자")
    
    # created_at: 비디오 레코드가 생성된 시간
    # DateTimeField를 사용하여 날짜와 시간을 저장하며, auto_now_add=True로 설정하여
    # 객체가 처음 생성될 때 자동으로 현재 시간이 기록되도록 합니다.
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creation Timestamp")

    # is_bookmarked: 북마크 여부 (0: 북마크 안 함, 1: 북마크)
    is_bookmarked = models.BooleanField(default=False, verbose_name="Is Bookmarked")

    character = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='videos', null=True, blank=True)

    thumbnail_url = models.TextField(null=True, blank=True)  # thumnail_url
    
    is_combined = models.BooleanField(default=False, verbose_name="Is Combined Video") # 병합된 영상 여부
    is_deleted = models.BooleanField(default=True, verbose_name="Is Deleted") # True: 저장, False: 삭제

    # Meta 클래스: 모델의 메타데이터 옵션을 정의합니다.
    class Meta:
        # 사실 여기는 관리자페이지 아니면 있어야 하는 메소드는 아닐거같긴 합니다 .
        # ordering: 기본 정렬 순서를 정의합니다. 여기서는 'created_at' 필드를 기준으로 내림차순 정렬합니다.
        # (가장 최근에 생성된 비디오가 먼저 오도록)
        ordering = ['-created_at']
        # verbose_name: 단수형 모델 이름을 지정합니다. Django 관리자 페이지 등에서 사용됩니다.
        verbose_name = "Video"
        # verbose_name_plural: 복수형 모델 이름을 지정합니다. Django 관리자 페이지 등에서 사용됩니다.
        verbose_name_plural = "Videos"

    # __str__ 메서드: 객체를 문자열로 표현할 때 사용됩니다.
    # Django 관리자 페이지 등에서 객체를 식별하는 데 유용합니다.
    def __str__(self):
        return f"{self.title} ({self.user.username if self.user else 'Anonymous'})"
