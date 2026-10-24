from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from celery import states
from django.core.cache import cache
from django.test import SimpleTestCase

from app.celery import app
from app.task_base import ENQUEUED_AT_HEADER, AppTask


@app.task(name="app.tests.test_task_base.probe", expires=90, cooldown=30)
def probe(item_id, flag=False):
    return item_id


@app.task(name="app.tests.test_task_base.exclusive_probe", exclusive=60)
def exclusive_probe(item_id):
    return item_id


@app.task(name="app.tests.test_task_base.plain_probe")
def plain_probe(item_id):
    return item_id


@app.task(name="app.tests.test_task_base.undeduped_probe", dedupe=False)
def undeduped_probe(item_id):
    return item_id


class _Broker:
    """Publish for real (no eager mode) into a mocked send_task."""

    def __init__(self, testcase):
        eager = app.conf.task_always_eager
        app.conf.task_always_eager = False
        testcase.addCleanup(setattr, app.conf, "task_always_eager", eager)
        patcher = patch.object(app, "send_task")
        self.send_task = patcher.start()
        testcase.addCleanup(patcher.stop)

    @property
    def sent(self):
        return [call.args[1] for call in self.send_task.call_args_list]

    @property
    def last_options(self):
        return self.send_task.call_args.kwargs


def _as_worker(task, **request):
    """Run ``task`` the way a worker would (not eager, not direct)."""
    request.setdefault("id", "message-1")
    request.setdefault("delivery_info", {"routing_key": "community"})
    task.push_request(called_directly=False, **request)
    return task


class AppTaskQueueingTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.broker = _Broker(self)

    def test_every_app_task_uses_the_base(self):
        self.assertIsInstance(probe, AppTask)
        self.assertIsInstance(app.tasks["celery.backend_cleanup"], AppTask)

    def test_one_queued_copy_per_call(self):
        probe.delay(1)
        rejected = probe.delay(1)
        probe.delay(2)
        self.assertEqual(self.broker.sent, [(1,), (2,)])
        self.assertEqual(rejected.state, states.REJECTED)

    def test_positional_and_keyword_calls_share_a_slot(self):
        probe.delay(1)
        probe.apply_async(kwargs={"item_id": 1})
        probe.apply_async(args=(1,), kwargs={"flag": False})
        self.assertEqual(len(self.broker.sent), 1)

    def test_message_carries_enqueue_time_and_expiry(self):
        probe.delay(1)
        options = self.broker.last_options
        self.assertIn(ENQUEUED_AT_HEADER, options["headers"])
        self.assertEqual(options["expires"], 90)

    def test_retries_chords_and_callbacks_always_queue(self):
        probe.delay(1)
        probe.apply_async((1,), retries=1)
        probe.apply_async((1,), group_id="g")
        probe.apply_async((1,), chord={"task": "x"})
        probe.apply_async((1,), link=plain_probe.si(9))
        self.assertEqual(len(self.broker.sent), 5)

    def test_opting_out(self):
        undeduped_probe.delay(1)
        undeduped_probe.delay(1)
        probe.delay(1)
        probe.apply_async((1,), dedupe=False)
        self.assertEqual(len(self.broker.sent), 4)
        self.assertNotIn("dedupe", self.broker.last_options)

    def test_celery_builtins_are_never_deduped(self):
        cleanup = app.tasks["celery.backend_cleanup"]
        cleanup.delay()
        cleanup.delay()
        self.assertEqual(len(self.broker.sent), 2)

    def test_a_started_copy_frees_the_slot(self):
        probe.delay(1)
        task_id = self.broker.last_options["task_id"]
        _as_worker(probe, id=task_id)
        try:
            self.assertEqual(probe(1), 1)
        finally:
            probe.pop_request()
        probe.delay(1)
        self.assertEqual(len(self.broker.sent), 2)

    def test_an_older_copy_does_not_free_a_newer_copys_slot(self):
        probe.delay(1)
        _as_worker(probe, id="some-older-message")
        try:
            probe(1)
        finally:
            probe.pop_request()
        probe.delay(1)
        self.assertEqual(len(self.broker.sent), 1)

    def test_cache_outage_queues_anyway(self):
        with patch("app.task_base.cache.add", side_effect=ConnectionError):
            probe.delay(1)
            probe.delay(1)
        self.assertEqual(len(self.broker.sent), 2)


class AppTaskLockTtlTestCase(SimpleTestCase):
    def test_expires_sets_the_lock_ttl(self):
        self.assertEqual(probe.queued_ttl({}), 90)
        self.assertEqual(probe.queued_ttl({"expires": 10}), 10)

    def test_queue_default_plus_countdown(self):
        # plain_probe routes to "community" (dedupe_ttl 3600s)
        self.assertEqual(plain_probe.queued_ttl({}), 3600)
        self.assertEqual(plain_probe.queued_ttl({"countdown": 120}), 3720)

    def test_eta_extends_the_ttl(self):
        eta = datetime.now(timezone.utc) + timedelta(minutes=10)
        ttl = plain_probe.queued_ttl({"eta": eta})
        self.assertAlmostEqual(ttl, 3600 + 600, delta=2)

    def test_fast_lane_locks_are_short(self):
        task = app.tasks["discord.outbox.post_discord_message_task"]
        self.assertEqual(task.queued_ttl({}), 5 * 60)


class AppTaskRunTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_redelivered_message_runs_once(self):
        _as_worker(plain_probe, id="m1")
        try:
            self.assertEqual(plain_probe(1), 1)
            self.assertIsNone(plain_probe(1))
        finally:
            plain_probe.pop_request()

    def test_a_retry_of_the_same_message_runs(self):
        _as_worker(plain_probe, id="m1", retries=0)
        try:
            self.assertEqual(plain_probe(1), 1)
        finally:
            plain_probe.pop_request()
        _as_worker(plain_probe, id="m1", retries=1)
        try:
            self.assertEqual(plain_probe(1), 1)
        finally:
            plain_probe.pop_request()

    def test_cooldown_skips_a_call_that_just_started(self):
        for message_id, item, expected in (
            ("m1", 1, 1),
            ("m2", 1, None),
            ("m3", 2, 2),
        ):
            _as_worker(probe, id=message_id)
            try:
                self.assertEqual(probe(item), expected)
            finally:
                probe.pop_request()

    def test_exclusive_skips_while_the_same_call_runs(self):
        cache.add(
            exclusive_probe.call_key("task-running", (1,), {}), "other", 60
        )
        _as_worker(exclusive_probe, id="m1")
        try:
            self.assertIsNone(exclusive_probe(1))
        finally:
            exclusive_probe.pop_request()
        _as_worker(exclusive_probe, id="m2")
        try:
            self.assertEqual(exclusive_probe(2), 2)
        finally:
            exclusive_probe.pop_request()
        self.assertIsNone(
            cache.get(exclusive_probe.call_key("task-running", (2,), {}))
        )

    def test_direct_and_eager_calls_skip_the_guards(self):
        self.assertEqual(probe(1), 1)
        self.assertEqual(probe(1), 1)
        self.assertEqual(probe.delay(1).get(), 1)
        self.assertEqual(probe.delay(1).get(), 1)

    def test_skips_are_counted(self):
        with patch("app.task_base.monitoring.record_task_skip") as record:
            _as_worker(plain_probe, id="m1")
            try:
                plain_probe(1)
                plain_probe(1)
            finally:
                plain_probe.pop_request()
        record.assert_called_once_with(plain_probe.name, "redelivered")

    def test_run_is_tagged_with_its_queue(self):
        with patch("app.task_base.monitoring.tag_task_run") as tag:
            _as_worker(plain_probe, id="m1")
            try:
                plain_probe(1)
            finally:
                plain_probe.pop_request()
        self.assertEqual(
            tag.call_args.args[0].delivery_info, {"routing_key": "community"}
        )

    def test_cache_outage_runs_the_task(self):
        with patch("app.task_base.cache.add", side_effect=ConnectionError):
            _as_worker(probe, id="m1")
            try:
                self.assertEqual(probe(1), 1)
                self.assertEqual(probe(1), 1)
            finally:
                probe.pop_request()
