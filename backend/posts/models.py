from django.contrib.auth.models import User
from django.db import models


# Create your models here.
class EveTag(models.Model):
    tag = models.CharField(max_length=100)

    def __str__(self):
        return str(self.tag)


class EvePost(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.title)


class EvePostImage(models.Model):
    post = models.ForeignKey(EvePost, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="post_images")

    def __str__(self):
        return str(self.post.title)


class EvePostTag(models.Model):
    post = models.ForeignKey(EvePost, on_delete=models.CASCADE)
    tag = models.ForeignKey(EveTag, on_delete=models.CASCADE)
