"""Write audit entries for staff actions made on the site."""

from audit.models import AuditEntry

SUMMARY_MAX = 255


def record_audit(user, summary: str, category: str = "other") -> AuditEntry:
    """Log who did what. The summary is cut to the column length."""
    return AuditEntry.objects.create(
        user=user,
        category=category,
        summary=summary[:SUMMARY_MAX],
    )
