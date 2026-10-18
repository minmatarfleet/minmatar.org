from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from app.celery import app
from app.locks import DedupedTask, overlap_guard, single_flight


@app.task(
    base=DedupedTask,
    expires=90,
    cooldown=30,
    name="app.tests.test_locks.deduped_probe",
)
def deduped_probe(item_id):
    return item_id


class SingleFlightTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_second_concurrent_caller_is_told_to_skip(self):
        with single_flight("test:lock", 60) as first:
            with single_flight("test:lock", 60) as second:
                self.assertTrue(first)
                self.assertFalse(second)
        with single_flight("test:lock", 60) as third:
            self.assertTrue(third)

    def test_does_not_release_a_lock_it_no_longer_owns(self):
        with single_flight("test:lock", 60):
            # Our TTL lapsed and another run took the lock.
            cache.set("test:lock", "someone-else", 60)
        self.assertEqual(cache.get("test:lock"), "someone-else")

    def test_cache_outage_runs_unguarded(self):
        with patch(
            "app.locks.cache.add", side_effect=ConnectionError("redis down")
        ):
            with single_flight("test:lock", 60) as acquired:
                self.assertTrue(acquired)


class OverlapGuardTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.body = MagicMock(return_value="ran")

        @overlap_guard(ttl=60, key="test:guard")
        def task():
            return self.body()

        self.task = task

    def test_skips_while_the_previous_run_holds_the_lock(self):
        cache.add("test:guard", "previous-run", 60)
        self.assertIsNone(self.task())
        self.body.assert_not_called()

    def test_runs_and_releases(self):
        self.assertEqual(self.task(), "ran")
        self.assertEqual(self.task(), "ran")
        self.assertIsNone(cache.get("test:guard"))

    def test_releases_when_the_run_raises(self):
        self.body.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.task()
        self.assertIsNone(cache.get("test:guard"))
        self.body.side_effect = None
        self.assertEqual(self.task(), "ran")

    def test_default_key_is_the_function_path(self):
        @overlap_guard(ttl=60)
        def some_task():
            return cache.get(
                f"task-lock:{__name__}.OverlapGuardTestCase."
                "test_default_key_is_the_function_path.<locals>.some_task"
            )

        self.assertIsNotNone(some_task())


class GuardedTaskNamesTestCase(SimpleTestCase):
    """Wrapping keeps the registered task names beat schedules point at."""

    def test_guarded_tasks_keep_their_names(self):
        # pylint: disable=import-outside-toplevel
        from campaigns import tasks as campaign_tasks
        from creators import tasks as creator_tasks
        from feed import tasks as feed_tasks
        from fleets import tasks as fleet_tasks

        for task in (
            fleet_tasks.update_fleet_instances,
            fleet_tasks.poll_active_fleet_implants,
            campaign_tasks.run_campaign_lifecycle,
            campaign_tasks.campaign_health,
            feed_tasks.detect_feed_clusters,
            creator_tasks.poll_creator_twitch_live,
        ):
            self.assertTrue(task.name.endswith(task.__name__), task.name)
            self.assertIn(task.name, app.tasks)
        self.assertEqual(
            fleet_tasks.update_fleet_instances.name,
            "fleets.tasks.update_fleet_instances",
        )


class DedupedTaskTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_queues_one_copy_per_arguments(self):
        eager = app.conf.task_always_eager
        app.conf.task_always_eager = False
        self.addCleanup(setattr, app.conf, "task_always_eager", eager)
        with patch.object(app, "send_task") as send_task:
            deduped_probe.delay(1)
            deduped_probe.delay(1)
            deduped_probe.delay(2)

        self.assertEqual(
            [call.args[1] for call in send_task.call_args_list],
            [(1,), (2,)],
        )
        # The lock lives exactly as long as the queued message.
        self.assertEqual(send_task.call_args.kwargs["expires"], 90)
        self.assertEqual(deduped_probe.once["timeout"], 90)

    def test_a_finished_run_frees_the_slot(self):
        self.assertEqual(deduped_probe.delay(1).get(), 1)
        self.assertEqual(deduped_probe.delay(1).get(), 1)

    def test_worker_skips_a_copy_whose_call_just_started(self):
        deduped_probe.push_request(called_directly=False)
        try:
            self.assertEqual(deduped_probe(1), 1)
            self.assertIsNone(deduped_probe(1))
            self.assertEqual(deduped_probe(2), 2)
        finally:
            deduped_probe.pop_request()

    def test_direct_calls_ignore_the_cooldown(self):
        self.assertEqual(deduped_probe(1), 1)
        self.assertEqual(deduped_probe(1), 1)

    def test_cache_outage_runs_the_copy(self):
        deduped_probe.push_request(called_directly=False)
        try:
            with patch(
                "app.locks.cache.add", side_effect=ConnectionError("down")
            ):
                self.assertEqual(deduped_probe(1), 1)
        finally:
            deduped_probe.pop_request()
