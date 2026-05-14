from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Patient
from game.models import CatAvatar

@receiver(post_save, sender=Patient)
def create_patient_avatar(sender, instance, created, **kwargs):
    if created:
        CatAvatar.objects.create(patient=instance)