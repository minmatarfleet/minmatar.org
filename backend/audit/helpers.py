"""Write audit entries for staff actions and config changes on the site."""

from audit.models import AuditEntry

SUMMARY_MAX = 255


def record_audit(user, summary: str, category: str = "other") -> AuditEntry:
    """Log who did what. The summary is cut to the column length."""
    return AuditEntry.objects.create(
        user=user,
        category=category,
        summary=summary[:SUMMARY_MAX],
    )


def record_change(user, summary: str) -> AuditEntry:
    """Log who changed a setting. Config edits use the ``other`` category."""
    return record_audit(user, summary, "other")
