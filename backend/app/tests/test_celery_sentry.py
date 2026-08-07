"""Unit tests for Celery Sentry before_send filter."""

from unittest import TestCase

from app.celery import _sentry_before_send


class SentryBeforeSendTestCase(TestCase):
    def test_drops_esi_refresh_impossible(self):
        event = {
            "logger": "esi.models",
            "logentry": {
                "message": "Refresh impossible for <Token>: InvalidGrantError"
            },
        }
        self.assertIsNone(_sentry_before_send(event, {}))

    def test_keeps_other_esi_models_errors(self):
        event = {
            "logger": "esi.models",
            "logentry": {"message": "Something else failed"},
        }
        self.assertIs(event, _sentry_before_send(event, {}))

    def test_keeps_non_esi_loggers(self):
        event = {
            "logger": "groups.tasks",
            "logentry": {"message": "Refresh impossible for someone"},
        }
        self.assertIs(event, _sentry_before_send(event, {}))
