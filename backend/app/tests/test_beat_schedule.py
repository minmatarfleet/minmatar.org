from datetime import timedelta

from celery.schedules import crontab, schedule
from django.conf import settings
from django.test import SimpleTestCase
from django_celery_beat.models import PeriodicTask
from django_celery_beat.schedulers import ModelEntry

from app.celery import app
from app.test import TestCase

FAST_SECONDS = 15 * 60


def _interval_seconds(entry_schedule) -> float:
    """Shortest gap between two runs of a beat schedule."""
    if isinstance(entry_schedule, crontab):
        if entry_schedule.day_of_week != set(range(7)):
            return 7 * 86400
        times = sorted(
            hour * 60 + minute
            for hour in entry_schedule.hour
            for minute in entry_schedule.minute
        )
        gaps = [b - a for a, b in zip(times, times[1:])]
        gaps.append(times[0] + 1440 - times[-1])
        return min(gaps) * 60
    if isinstance(entry_schedule, schedule):
        return entry_schedule.run_every.total_seconds()
    raise AssertionError(f"Unknown schedule {entry_schedule!r}")


class BeatScheduleTestCase(SimpleTestCase):
    def test_every_beat_task_is_registered(self):
        app.loader.import_default_modules()
        missing = sorted(
            entry["task"]
            for entry in settings.CELERYBEAT_SCHEDULE.values()
            if entry["task"] not in app.tasks
        )
        self.assertEqual(missing, [])

    def test_fast_entries_expire_within_their_interval(self):
        for name, entry in settings.CELERYBEAT_SCHEDULE.items():
            interval = _interval_seconds(entry["schedule"])
            expires = entry.get("options", {}).get("expire_seconds")
            with self.subTest(name):
                if interval <= FAST_SECONDS:
                    self.assertIsNotNone(expires)
                if expires is not None:
                    self.assertGreater(expires, 0)
                    self.assertLessEqual(expires, max(interval, 12 * 3600))

    def test_interval_helper(self):
        self.assertEqual(_interval_seconds(crontab(minute="*/15")), 900)
        self.assertEqual(
            _interval_seconds(crontab(minute="*", hour="*/1")), 60
        )
        self.assertEqual(
            _interval_seconds(crontab(minute="5,35", hour="*")), 1800
        )
        self.assertEqual(
            _interval_seconds(schedule(timedelta(seconds=30))), 30
        )


class BeatExpiryReachesTheDatabaseTestCase(TestCase):
    def test_database_scheduler_stores_the_expiry(self):
        entry = settings.CELERYBEAT_SCHEDULE["[Misc] Check Fleets"]
        model_entry = ModelEntry.from_entry(
            "[Misc] Check Fleets", app=app, **entry
        )
        task = PeriodicTask.objects.get(name="[Misc] Check Fleets")
        self.assertEqual(task.expire_seconds, 30)
        self.assertEqual(model_entry.options["expires"], 30)
