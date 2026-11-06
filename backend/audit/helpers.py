"""Write config-change entries to the audit log."""

from audit.models import AuditEntry

SUMMARY_MAX = 255


def record_change(user, summary: str) -> AuditEntry:
    """Log who changed a setting. Config edits use the ``other`` category."""
    return AuditEntry.objects.create(
        user=user, category="other", summary=summary[:SUMMARY_MAX]
    )
