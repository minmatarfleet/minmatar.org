from io import StringIO
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase


def _project_app_labels():
    """Labels of the apps that live in this repo (not third-party ones)."""
    base_dir = Path(settings.BASE_DIR).resolve()
    return [
        config.label
        for config in apps.get_app_configs()
        if base_dir in Path(config.path).resolve().parents
    ]


class PendingMigrationsTestCase(TestCase):
    """Fail when a model change has no migration.

    A missing migration means the model and the deployed schema can drift
    apart. Run `manage.py makemigrations <app>` and commit the result.
    """

    def test_no_pending_model_changes(self):
        labels = _project_app_labels()
        self.assertIn("campaigns", labels)
        out = StringIO()
        try:
            call_command(
                "makemigrations",
                *labels,
                check=True,
                dry_run=True,
                stdout=out,
                stderr=out,
            )
        except SystemExit:
            self.fail(
                "Models have changes without a migration. Run "
                "`manage.py makemigrations` and commit the files:\n"
                + out.getvalue()
            )
