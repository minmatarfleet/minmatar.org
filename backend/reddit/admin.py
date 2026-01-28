from django.contrib import admin

from reddit.models import RedditScheduledPost


class RedditPostAdmin(admin.ModelAdmin):
    """Custom admin model for RedditScheduledPost entities"""

    list_display = [
        "title",
        "subreddit",
        "posting_day",
        "last_post_at",
    ]


admin.site.register(RedditScheduledPost, RedditPostAdmin)
