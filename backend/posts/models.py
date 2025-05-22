from django.contrib.auth.models import User
from django.db import models


# Create your models here.
class EveTag(models.Model):
    tag = models.CharField(max_length=100)

    def __str__(self):
        return str(self.tag)


class EvePost(models.Model):
    """
    Model for the blog post
    """

    state_choices = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("trash", "Trash"),
    ]
    state = models.CharField(
        max_length=10, choices=state_choices, default="draft"
    )
    title = models.CharField(max_length=250, unique=True)
    seo_description = models.CharField(max_length=300)
    slug = models.SlugField(max_length=100)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(EveTag, blank=True)

    def __str__(self):
        return str(self.title)

    @staticmethod
    def generate_slug(title):
        """
        Convert the title into a slug
        """
        return title.lower().replace(" ", "-")


class EvePostImage(models.Model):
    post = models.ForeignKey(EvePost, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="post_images")

    def __str__(self):
        return str(self.post.title)
