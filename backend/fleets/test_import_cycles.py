"""Fleet helpers must import cleanly on their own, in a fresh interpreter.

``fleets.helpers.npsi_actions`` imports ``fleets.endpoints.helpers``, and the
NPSI routes import ``npsi_actions`` back. That only works while importing a
``fleets.endpoints`` module does not pull in every route module, so this
guards against moving the router composition back into the package init.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BACKEND_DIR = Path(__file__).resolve().parents[1]

MODULES = [
    "fleets.helpers.npsi_local",
    "fleets.helpers.npsi_actions",
    "fleets.helpers.schedule_fleet",
    "fleets.endpoints.npsi.auth",
]


class FleetImportCycleTest(SimpleTestCase):
    def test_modules_import_cold(self):
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": settings.SETTINGS_MODULE,
        }
        for module in MODULES:
            with self.subTest(module=module):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"import django; django.setup(); import {module}",
                    ],
                    cwd=BACKEND_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr[-2000:])
