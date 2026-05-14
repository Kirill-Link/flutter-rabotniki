from django.db import models
from django.contrib.auth.models import AbstractUser
import string
import random

class User(AbstractUser):
    middle_name = models.CharField("Отчество", max_length=255, blank=True)
    clinic_name = models.CharField("Название клиники", max_length=255, blank=True)
    is_doctor = models.BooleanField("Роль: Врач", default=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.clinic_name})"
