from unittest.mock import MagicMock

from django.test import SimpleTestCase

import esi.views

from eveonline.esi_view_patches import patch_esi_receive_callback


def _make_recording_view(return_value):
    """A plain function (not a Mock) so the patch's idempotency marker
    check behaves like it would against the real django-esi view, instead
    of a Mock auto-vivifying a truthy attribute for any name."""
    calls = []

    def _view(request, *args, **kwargs):
        calls.append((request, args, kwargs))
        return return_value

    _view.calls = calls
    return _view


class EsiReceiveCallbackPatchTest(SimpleTestCase):
    """REST-API-A2: a session with no key must not crash the callback view."""

    def setUp(self):
        super().setUp()
        self._original_receive_callback = esi.views.receive_callback
        self.addCleanup(
            setattr,
            esi.views,
            "receive_callback",
            self._original_receive_callback,
        )

    def test_creates_session_when_key_missing_before_delegating(self):
        original = _make_recording_view("response")
        esi.views.receive_callback = original

        patch_esi_receive_callback()

        request = MagicMock()
        request.session.session_key = None

        result = esi.views.receive_callback(request)

        request.session.create.assert_called_once()
        self.assertEqual(len(original.calls), 1)
        self.assertIs(original.calls[0][0], request)
        self.assertEqual(result, "response")

    def test_does_not_create_session_when_key_present(self):
        original = _make_recording_view("response")
        esi.views.receive_callback = original

        patch_esi_receive_callback()

        request = MagicMock()
        request.session.session_key = "abcdef"

        esi.views.receive_callback(request)

        request.session.create.assert_not_called()
        self.assertEqual(len(original.calls), 1)

    def test_patch_is_idempotent(self):
        original = _make_recording_view("response")
        esi.views.receive_callback = original

        patch_esi_receive_callback()
        patched_once = esi.views.receive_callback

        patch_esi_receive_callback()

        self.assertIs(patched_once, esi.views.receive_callback)
