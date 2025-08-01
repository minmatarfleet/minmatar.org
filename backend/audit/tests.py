from app.test import TestCase

from audit.models import AuditEntry


class AuditTestCase(TestCase):
    """Test cases for the auto log"""

    def test_simple_audit(self):
        entry = AuditEntry.objects.create(
            user=self.user,
            category="other",
            summary="Test event",
        )
        self.assertIsNotNone(entry.created_at)
