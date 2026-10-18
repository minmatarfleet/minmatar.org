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
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        help_text="Optional campaign this post (propaganda, write-up) is for.",
    )
    host_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosted_posts",
        help_text="Tribe group this post is published as.",
    )
    members_only = models.BooleanField(
        default=False,
        help_text="Only the host group's members (and its managers) see it.",
    )
    announced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the bot announced the post in the group's channel.",
    )
    tribe_groups = models.ManyToManyField(
        "tribes.TribeGroup",
        blank=True,
        related_name="posts",
        help_text="Optional tribe groups this post is associated with.",
    )

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
