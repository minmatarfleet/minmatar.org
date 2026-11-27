"""Tasks: what waits on each pilot, work shared by a team, and projects.

Two kinds of task share one table:

- automatic tasks are opened and closed by the site (``taskboard.rules``)
  from things it already tracks, such as a broken ESI token or a pending
  application. Their ``rule`` and ``source_key`` identify the thing.
- assigned tasks are written by a person, optionally inside a project.

A task belongs to one person (``user``) or is shared by a team
(``team_kind``/``team_id``/``team_role``) until someone takes it.
"""

from django.contrib.auth.models import User
from django.db import models


class Weight(models.TextChoices):
    # Someone is waiting on the pilot. Counts in the badge and leader views.
    NEEDS_YOU = "needs_you", "Needs you"
    # Optional. Never counted, never shown to leaders by name.
    SUGGESTION = "suggestion", "Suggestion"


class TeamKind(models.TextChoices):
    NONE = "", "No team"
    CORPORATION = "corporation", "Corporation"
    TRIBE_GROUP = "tribe_group", "Tribe group"
    # A manage screen: everyone who can reach it (team_role holds its key).
    STAFF = "staff", "Staff"


class Task(models.Model):
    KIND_AUTOMATIC = "automatic"
    KIND_ASSIGNED = "assigned"
    KIND_CHOICES = [
        (KIND_AUTOMATIC, "Automatic"),
        (KIND_ASSIGNED, "Assigned"),
    ]

    STATUS_OPEN = "open"
    # The pilot or the site finished it.
    STATUS_DONE = "done"
    # A suggestion that sat too long, or an assigned task nobody kept.
    STATUS_STOPPED = "stopped"
    # Withdrawn by whoever made it, or its project was removed.
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_DONE, "Done"),
        (STATUS_STOPPED, "Stopped asking"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    WHEN_THIS_WEEK = "this_week"
    WHEN_NO_RUSH = "no_rush"
    WHEN_DATE = "date"
    WHEN_CHOICES = [
        (WHEN_THIS_WEEK, "This week"),
        (WHEN_NO_RUSH, "No rush"),
        (WHEN_DATE, "By a set date"),
    ]

    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    # Automatic tasks: the rule that opened it and the thing it is about
    # ("character:9001", "corporation:98726134").
    rule = models.CharField(max_length=64, blank=True, default="")
    # Null on assigned tasks, so the unique key below only binds automatic
    # ones (MySQL has no conditional unique constraints).
    source_key = models.CharField(
        max_length=128, null=True, blank=True, default=None
    )

    title = models.CharField(max_length=200)
    # One line under the title.
    detail = models.CharField(max_length=300, blank=True, default="")
    body = models.TextField(blank=True, default="")
    link_url = models.CharField(max_length=500, blank=True, default="")
    link_label = models.CharField(max_length=64, blank=True, default="")
    weight = models.CharField(
        max_length=16, choices=Weight.choices, default=Weight.NEEDS_YOU
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="board_tasks",
    )
    team_kind = models.CharField(
        max_length=16, choices=TeamKind.choices, blank=True, default=""
    )
    team_id = models.BigIntegerField(null=True, blank=True)
    # Who in the team: "leaders", "recruiters", "ceo", or a manage screen key.
    team_role = models.CharField(max_length=64, blank=True, default="")
    team_label = models.CharField(max_length=128, blank=True, default="")
    claimed_at = models.DateTimeField(null=True, blank=True)

    project = models.ForeignKey(
        "Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tasks",
    )
    stage = models.ForeignKey(
        "ProjectStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    waiting_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocks",
    )

    when = models.CharField(
        max_length=16, choices=WHEN_CHOICES, default=WHEN_THIS_WEEK
    )
    due_date = models.DateField(null=True, blank=True)
    # "" or "weekly:<0-6>" (Monday is 0). The next copy opens when this
    # one closes, so a missed week never stacks up.
    recurrence = models.CharField(max_length=16, blank=True, default="")

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    snoozed_until = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField()
    last_activity_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    close_note = models.CharField(max_length=200, blank=True, default="")
    # Assigned tasks untouched for a while ask their author once.
    still_needed_asked_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_board_tasks",
    )
    thanked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="thanked_board_tasks",
    )
    thanked_at = models.DateTimeField(null=True, blank=True)
    # A leader's one reminder (a Discord DM), at most once per task.
    reminded_at = models.DateTimeField(null=True, blank=True)
    reminded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminded_board_tasks",
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["team_kind", "team_id", "status"]),
            models.Index(fields=["rule", "status"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["status", "closed_at"]),
        ]
        constraints = [
            # One row per automatic thing per pilot. Team tasks (no user
            # until someone takes one) are kept to one row by the sync.
            models.UniqueConstraint(
                fields=["rule", "source_key", "user"],
                name="uniq_board_task_source_user",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def is_team_task(self) -> bool:
        return bool(self.team_kind) and self.user_id is None


class TaskComment(models.Model):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ProjectTemplate(models.Model):
    """A reusable project: its stages and tasks (``TemplateTask``)."""

    KIND_CAMPAIGN = "campaign"
    KIND_DOCTRINE = "doctrine"
    KIND_TOWN_HALL = "town_hall"
    KIND_CHOICES = [
        (KIND_CAMPAIGN, "Campaign"),
        (KIND_DOCTRINE, "New doctrine"),
        (KIND_TOWN_HALL, "Town hall"),
    ]

    kind = models.CharField(max_length=16, choices=KIND_CHOICES, unique=True)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=200, blank=True, default="")
    position = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return str(self.name)


class TemplateTask(models.Model):
    # "lead" (the project lead) or "screen:<manage screen key>": up for
    # grabs to everyone who can reach that screen.
    GOES_TO_LEAD = "lead"

    template = models.ForeignKey(
        ProjectTemplate, on_delete=models.CASCADE, related_name="tasks"
    )
    stage = models.CharField(max_length=64)
    position = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=200)
    goes_to = models.CharField(max_length=64, default=GOES_TO_LEAD)
    # Days from the project start (negative: before it starts). None: no
    # date, the task is "No rush".
    offset_days = models.SmallIntegerField(null=True, blank=True)
    recurrence = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.template}: {self.title}"


class Project(models.Model):
    STATUS_OPEN = "open"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_FINISHED, "Finished"),
    ]

    name = models.CharField(max_length=120)
    template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    lead = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="led_projects"
    )
    # Who it belongs to: the alliance (blank), a corporation or a group.
    team_kind = models.CharField(
        max_length=16, choices=TeamKind.choices, blank=True, default=""
    )
    team_id = models.BigIntegerField(null=True, blank=True)
    team_label = models.CharField(max_length=128, blank=True, default="")
    link_url = models.CharField(max_length=500, blank=True, default="")
    link_label = models.CharField(max_length=64, blank=True, default="")
    starts_on = models.DateField(null=True, blank=True)
    # A target, not a deadline.
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "target_date", "name"]

    def __str__(self):
        return str(self.name)


class ProjectStage(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="stages"
    )
    name = models.CharField(max_length=64)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.project}: {self.name}"


class ProjectUpdate(models.Model):
    HEALTH_ON_TRACK = "on_track"
    HEALTH_AT_RISK = "at_risk"
    HEALTH_OFF_TRACK = "off_track"
    HEALTH_CHOICES = [
        (HEALTH_ON_TRACK, "On track"),
        (HEALTH_AT_RISK, "At risk"),
        (HEALTH_OFF_TRACK, "Off track"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="updates"
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    health = models.CharField(max_length=16, choices=HEALTH_CHOICES)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TaskRuleSetting(models.Model):
    """Admin overrides for an automatic rule (defaults in rules.py)."""

    rule = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)
    # Suggestions stop asking after this many days. None: never.
    stop_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    # A taken team task returns to "up for grabs" after this many quiet
    # days. None: never.
    claim_expires_days = models.PositiveSmallIntegerField(
        null=True, blank=True
    )
    # A leader may remind a pilot once, after this many days. None: the
    # default (14).
    remind_after_days = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.rule)


class TaskPreferences(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="task_preferences"
    )
    show_suggestions = models.BooleanField(default=True)
    # The pilot paused everything (time away). An On Leave community
    # status pauses tasks too.
    paused = models.BooleanField(default=False)
    # Quiet hours, as EVE (UTC) hours 0-23. Messages that fall inside wait
    # and go out together when they end. Both unset: no quiet hours.
    quiet_start = models.PositiveSmallIntegerField(null=True, blank=True)
    quiet_end = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} task preferences"


class TaskDigestSettings(models.Model):
    """When the weekly list goes out. One row (pk 1)."""

    enabled = models.BooleanField(default=True)
    # Monday is 0.
    weekday = models.PositiveSmallIntegerField(default=6)
    # EVE (UTC) hour.
    hour = models.PositiveSmallIntegerField(default=17)

    class Meta:
        verbose_name_plural = "Task digest settings"

    def __str__(self):
        return "Weekly task list"

    @classmethod
    def load(cls) -> "TaskDigestSettings":
        row, _ = cls.objects.get_or_create(pk=1)
        return row


class TaskMessageHold(models.Model):
    """A task message held during the pilot's quiet hours."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="held_task_messages"
    )
    type_key = models.CharField(max_length=64)
    context = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
