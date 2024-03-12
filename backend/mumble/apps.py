from django.apps import AppConfig
from django.db.models.signals import post_save

def create_mumble_access(sender, instance, created, **kwargs):
    if created:
        from .models import MumbleAccess
        MumbleAccess.objects.create_mumble_access(instance)

class MumbleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mumble'

    def ready(self):
        from django.contrib.auth.models import User

        post_save.connect(create_mumble_access, sender=User, dispatch_uid="create_mumble_access")
