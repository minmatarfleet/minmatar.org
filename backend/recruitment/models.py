from django.conf import settings
from django.db import models


class ForumRecruitmentPost(models.Model):
    """
    A corporation's recruitment thread in the EVE Online forums'
    Recruitment Center. Unlike Reddit, the thread is never re-posted: the
    corporation keeps one thread and bumps it.
    """

    corporation = models.OneToOneField(
        "eveonline.EveCorporation",
        on_delete=models.CASCADE,
        related_name="forum_recruitment_post",
    )
    url = models.URLField(
        help_text="Canonical thread URL: "
        "https://forums.eveonline.com/t/<slug>/<topic_id>",
    )
    topic_id = models.PositiveIntegerField(
        help_text="Discourse topic id, parsed from the URL."
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Thread title from the forum; blank if it couldn't be "
        "fetched.",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_bumped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.corporation}: {self.title or self.url}"
