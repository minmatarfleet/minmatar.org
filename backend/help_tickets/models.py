from django.contrib.auth.models import User
from django.db import models


class HelpRequestCategory(models.Model):
    """
    A selectable help topic in #help.

    Link to a TribeGroup for tribe routing (chief is mentioned automatically),
    and/or assign specific users to mention. General categories use assignees only.
    """

    title = models.CharField(
        max_length=100,
        help_text='Dropdown label (e.g. "Contact the freighter team").',
    )
    description = models.TextField(
        blank=True,
        help_text="Shown in the ticket thread welcome message.",
    )
    code = models.CharField(
        max_length=64,
        unique=True,
        help_text="Stable slug for thread names (e.g. market.freighters).",
    )
    tribe_group = models.OneToOneField(
        "tribes.TribeGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="help_request_category",
    )
    assignees = models.ManyToManyField(
        User,
        blank=True,
        related_name="help_request_categories",
        help_text="Users to @mention when a ticket is opened.",
    )
    section = models.CharField(
        max_length=128,
        blank=True,
        help_text="Select-menu grouping label. Defaults to tribe name when linked.",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "title"]
        verbose_name_plural = "help request categories"

    def save(self, *args, **kwargs):
        if self.tribe_group_id and not self.code:
            self.code = self.tribe_group.code
        if self.tribe_group_id and not self.description:
            self.description = self.tribe_group.description
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class HelpTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
    ]

    category = models.ForeignKey(
        HelpRequestCategory,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    opener_discord_id = models.BigIntegerField()
    opener = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="help_tickets_opened",
    )
    thread_id = models.BigIntegerField(unique=True)
    thread_name = models.CharField(max_length=100)
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_discord_id = models.BigIntegerField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="help_tickets_closed",
    )
    close_reason = models.TextField(blank=True)

    def __str__(self):
        return f"HelpTicket #{self.pk} ({self.status}) — {self.thread_name}"

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(
                fields=["category", "opened_at"],
                name="help_tickets_cat_opened",
            ),
            models.Index(
                fields=["status", "opened_at"],
                name="help_tickets_status_opened",
            ),
        ]


class HelpTicketPanel(models.Model):
    """Singleton storing the deployed #help ticket panel message."""

    channel_id = models.BigIntegerField()
    message_id = models.BigIntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk and HelpTicketPanel.objects.exists():
            raise ValueError("Only one HelpTicketPanel instance is allowed.")
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        panel, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"channel_id": 0},
        )
        return panel

    def __str__(self):
        return f"HelpTicketPanel channel={self.channel_id} message={self.message_id}"
