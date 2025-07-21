from django.db import models

# Create your models here.
class Book(models.Model):
    # Book 모델의 속성 정의
    title = models.CharField(max_length=255) # 책 제목
    content = models.TextField(max_length=1000, null=False, blank=False) # 책 내용
    pdf_url = models.URLField(max_length=500, null=True, blank=True) # S3에 저장된 PDF URL
    created_at = models.DateTimeField(auto_now_add=True) # 생성일자 - 자동으로 관리 
    updated_at = models.DateTimeField(auto_now=True) # 수정일자 - 자동으로 관리
    is_deleted = models.BooleanField(default=False) # 삭제 여부 - 기본값은 False(0)

    class Meta:
        db_table = 'books'
        verbose_name = '책'
        verbose_name_plural = '책들'
        ordering = ['-created_at']  # 최신순 정렬

    def __str__(self):
        return self.title

