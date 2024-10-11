from django.contrib import admin

from .models import EvePost, EvePostImage, EveTag

# Register your models here.
admin.site.register(EvePost)
admin.site.register(EveTag)
admin.site.register(EvePostImage)