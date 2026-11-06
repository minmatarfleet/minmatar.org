from django.contrib.admin.apps import AdminConfig

from app.admin_standards import apply_admin_standards


class StandardAdminConfig(AdminConfig):
    """Django admin that applies the house standards after autodiscover."""

    def ready(self):
        super().ready()
        apply_admin_standards()
