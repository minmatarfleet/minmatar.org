from django.contrib import admin

from .models import EvePost, EvePostImage, EvePostTag, EveTag

# Register your models here.
admin.site.register(EvePost)
admin.site.register(EveTag)
admin.site.register(EvePostImage)
admin.site.register(EvePostTag)
