from django.db import models


class RedditScheduledPost(models.Model):
    """
    A scheduled reddit post.
    """

    subreddit = models.CharField(max_length=250)
    title = models.CharField(max_length=250)
    content = models.TextField()
    flair = models.CharField(max_length=80, null=True, blank=True)

    day_choices = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]

    posting_day = models.CharField(max_length=12, choices=day_choices)

    last_post_at = models.DateTimeField(null=True, blank=True)
    latest_comment_url = models.CharField(max_length=80, null=True, blank=True)
    latest_fullname = models.CharField(max_length=20, null=True, blank=True)

    discord_channel = models.CharField(max_length=250, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
