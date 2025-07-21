from django.db import models
from books.models import Book # Book 모델의 book_id 속성을 사용하기 위해 호출

# Create your models here.
'''캐릭터 모델 정의'''
class Character(models.Model):
    # Character 모델의 속성 정의
    
    characterName = models.CharField(max_length=100)
    isMain = models.BooleanField(default=False) # 주인공 여부 - 기본값은 False(0, 조연)
    age = models.IntegerField(null=False, blank=False) # 나이
    gender = models.CharField(max_length=10, null=False, blank=False) # 성별
    characterDescription = models.TextField(max_length=500, null=False, blank=False) # 캐릭터 설명

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False) # 삭제 여부 - 기본값은 False(0)

    # Book 모델과의 관계 설정
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='characters')


    def __str__(self):
        return f"{self.characterName} ({self.book.title})"



'''캐릭터_장면 모델 정의'''
class CharacterScene(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='scenes')
    scene_content = models.TextField(max_length=500, null=False, blank=False)
    start_page = models.IntegerField(null=False, blank=False)
    finish_page = models.IntegerField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.character.characterName} - 장면 {self.scene_number}"