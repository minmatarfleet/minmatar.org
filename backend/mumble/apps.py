from django.apps import AppConfig
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import MumbleAccess

@receiver(post_save, sender=User, dispatch_uid="create_mumble_access")
def create_mumble_access(sender, instance, created, **kwargs):
    if created:
        MumbleAccess.objects.create_mumble_access(instance)

class MumbleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mumble'