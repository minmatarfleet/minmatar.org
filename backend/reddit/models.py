from django.db import models


class RedditScheduledPost(models.Model):
    """
    A scheduled reddit post.
    """

    subreddit = models.CharField(max_length=250)
    title = models.CharField(max_length=250)
    content = models.TextField()

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
    last_post_at = models.DateTimeField()

    updated_at = models.DateTimeField(auto_now=True)
