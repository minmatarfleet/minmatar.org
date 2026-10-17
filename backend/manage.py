#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    """Run administrative tasks."""
    default_settings = "app.settings"
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Tests default to SQLite with the network guard, never to the
        # MySQL settings and whatever Discord/ESI tokens .env holds.
        # An explicit --settings still wins.
        default_settings = "app.settings_test"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)
    try:
        import dotenv  # noqa
    except ImportError:
        pass
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
