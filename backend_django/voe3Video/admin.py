from django.contrib import admin
from django.contrib import messages
from .models import Video
from .veo_service import generate_signed_url

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_id', 'created_at', 'is_bookmarked')
    list_filter = ('is_bookmarked', 'created_at')
    search_fields = ('title', 'prompt', 'user_id')
    list_editable = ('is_bookmarked',)

    @admin.action(description='선택된 비디오의 서명된 URL 재생성')
    def regenerate_signed_urls(self, request, queryset):
        updated_count = 0
        for video in queryset:
            try:
                signed_url = generate_signed_url(video.video_uri)
                if signed_url:
                    updated_count += 1
                else:
                    self.message_user(request, f"비디오 '{video.title}'의 서명된 URL 재생성 실패.", level=messages.ERROR)
            except Exception as e:
                self.message_user(request, f"비디오 '{video.title}' 처리 중 오류 발생: {e}", level=messages.ERROR)

        if updated_count > 0:
            self.message_user(request, f"{updated_count}개의 비디오 서명된 URL이 성공적으로 재생성되었습니다.", level=messages.SUCCESS)
        else:
            self.message_user(request, "재생성된 서명된 URL이 없습니다.", level=messages.WARNING)

    actions = [regenerate_signed_urls]
