from __future__ import annotations

from celery_once import AlreadyQueued
from django.core.cache import cache
from django.test import TestCase

from app.celery_once_backend import DjangoBackend


class CeleryOnceBackendTestCase(TestCase):
    def tearDown(self):
        cache.clear()

    def test_raise_or_lock_acquires(self):
        DjangoBackend.raise_or_lock("celery-once-test", 60)
        self.assertFalse(cache.add("celery-once-test", "lock", timeout=60))

    def test_raise_or_lock_raises_without_ttl_support(self):
        DjangoBackend.raise_or_lock("celery-once-test", 45)
        with self.assertRaises(AlreadyQueued) as ctx:
            DjangoBackend.raise_or_lock("celery-once-test", 45)
        self.assertEqual(ctx.exception.countdown, 45)
