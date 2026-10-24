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


class ScoutOutreach(models.Model):
    """
    One reply the recruitment scout drafted for a pilot's looking-for-corp
    post. The code rides in the reply's links
    (my.minmatar.org/go/<code>/<target>), so a click traces back here.
    """

    SURFACE_CHOICES = [
        ("evejobs", "r/evejobs"),
        ("eve", "r/eve"),
        ("forums", "EVE forums"),
    ]

    code = models.CharField(max_length=12, unique=True)
    surface = models.CharField(max_length=16, choices=SURFACE_CHOICES)
    thread_url = models.URLField(
        max_length=500,
        unique=True,
        help_text="The pilot's thread. One code per thread: drafting "
        "again for the same thread reuses it.",
    )
    prospect = models.CharField(
        max_length=100,
        blank=True,
        help_text="The pilot's Reddit or forum name.",
    )
    seat = models.CharField(
        max_length=64,
        blank=True,
        help_text="Where the scout routed them: a ticker (TDT, L3ARN), "
        "MFA, or FW redirect.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} {self.get_surface_display()} {self.thread_url}"


class ScoutOutreachClick(models.Model):
    """A visit through one of a scout reply's tracked links."""

    outreach = models.ForeignKey(
        ScoutOutreach, on_delete=models.CASCADE, related_name="clicks"
    )
    target = models.CharField(
        max_length=32, help_text="discord, learning, corporations..."
    )
    visitor = models.CharField(
        max_length=64,
        help_text="Keyed hash of the client IP, for counting unique "
        "visitors. The IP itself is not stored.",
    )
    user_agent = models.CharField(max_length=255, blank=True)
    is_bot = models.BooleanField(
        default=False,
        help_text="Link-preview crawlers (Discourse onebox, Reddit, "
        "Discord) and scripts. Not counted as clicks.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["outreach", "target"])]

    def __str__(self):
        return f"{self.outreach.code}/{self.target}"
