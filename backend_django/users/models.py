from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    short_description = models.TextField("소개글", blank=True)