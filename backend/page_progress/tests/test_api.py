"""Tests for page progress API endpoints and admin roster."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase

from page_progress.admin import UserPageProgressAdmin
from page_progress.helpers import MAX_IMPORT_PAGES
from page_progress.models import UserPageProgress, UserPageSectionProgress

BASE = "/api/page-progress"
PAGE_KEY = "guides/bookmarks"
VERSION = "abc123version"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class PageProgressApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="reader",
            password="unused",
        )
        self.token = _make_token(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.sections = ["intro", "basics", "advanced"]

    def _status_url(self, page_key=PAGE_KEY, version=VERSION, sections=None):
        sections = self.sections if sections is None else sections
        qs = f"?version={version}&sections={','.join(sections)}"
        return f"{BASE}/{page_key}{qs}"

    def _read_url(self, section_id, page_key=PAGE_KEY):
        return f"{BASE}/{page_key}/sections/{section_id}/read"

    def _ack_url(self, page_key=PAGE_KEY):
        return f"{BASE}/{page_key}/ack"

    def test_unauthenticated_returns_401(self):
        r = self.client.get(self._status_url())
        self.assertEqual(r.status_code, 401)

    def test_empty_status_for_new_user(self):
        r = self.client.get(self._status_url(), **self.auth)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["page_key"], PAGE_KEY)
        self.assertEqual(data["read_sections"], [])
        self.assertEqual(data["missing_sections"], self.sections)
        self.assertEqual(data["read_count"], 0)
        self.assertEqual(data["section_total"], 3)
        self.assertEqual(data["percent"], 0)
        self.assertFalse(data["is_acknowledged"])

    def test_section_read_is_idempotent(self):
        payload = {
            "version": VERSION,
            "page_title": "Bookmarks",
            "section_total": 3,
        }
        r1 = self.client.post(
            self._read_url("intro"),
            data=payload,
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["created"])
        self.assertEqual(r1.json()["percent"], 33)

        r2 = self.client.post(
            self._read_url("intro"),
            data=payload,
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["created"])
        self.assertEqual(
            UserPageSectionProgress.objects.filter(
                user=self.user,
                page_key=PAGE_KEY,
                section_id="intro",
                version=VERSION,
            ).count(),
            1,
        )

    def test_ack_rejected_when_sections_missing(self):
        self.client.post(
            self._read_url("intro"),
            data={
                "version": VERSION,
                "page_title": "Bookmarks",
                "section_total": 3,
            },
            content_type="application/json",
            **self.auth,
        )
        r = self.client.post(
            self._ack_url(),
            data={
                "version": VERSION,
                "sections": self.sections,
                "page_title": "Bookmarks",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Missing", r.json()["detail"])

    def test_ack_succeeds_after_all_sections_read(self):
        payload = {
            "version": VERSION,
            "page_title": "Bookmarks",
            "section_total": 3,
        }
        for section_id in self.sections:
            self.client.post(
                self._read_url(section_id),
                data=payload,
                content_type="application/json",
                **self.auth,
            )

        r = self.client.post(
            self._ack_url(),
            data={
                "version": VERSION,
                "sections": self.sections,
                "page_title": "Bookmarks",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["is_acknowledged"])
        self.assertEqual(data["percent"], 100)

        progress = UserPageProgress.objects.get(
            user=self.user,
            page_key=PAGE_KEY,
            version=VERSION,
        )
        self.assertIsNotNone(progress.acknowledged_at)
        self.assertEqual(progress.page_title, "Bookmarks")

    def test_version_change_isolates_old_progress(self):
        payload = {
            "version": VERSION,
            "page_title": "Bookmarks",
            "section_total": 3,
        }
        for section_id in self.sections:
            self.client.post(
                self._read_url(section_id),
                data=payload,
                content_type="application/json",
                **self.auth,
            )
        self.client.post(
            self._ack_url(),
            data={
                "version": VERSION,
                "sections": self.sections,
                "page_title": "Bookmarks",
            },
            content_type="application/json",
            **self.auth,
        )

        new_version = "newversion456"
        r = self.client.get(
            self._status_url(version=new_version),
            **self.auth,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["read_sections"], [])
        self.assertEqual(data["percent"], 0)
        self.assertFalse(data["is_acknowledged"])

    def test_import_unions_sections_and_ack(self):
        # Existing server progress
        self.client.post(
            self._read_url("intro"),
            data={
                "version": VERSION,
                "page_title": "Bookmarks",
                "section_total": 3,
            },
            content_type="application/json",
            **self.auth,
        )

        r = self.client.post(
            f"{BASE}/import",
            data={
                "pages": [
                    {
                        "page_key": PAGE_KEY,
                        "version": VERSION,
                        "page_title": "Bookmarks",
                        "section_total": 3,
                        "read_sections": ["intro", "basics", "advanced"],
                        "is_acknowledged": True,
                    },
                    {
                        "page_key": "alliance/values",
                        "version": "v1",
                        "page_title": "Values",
                        "section_total": 2,
                        "read_sections": ["a"],
                        "is_acknowledged": False,
                    },
                ]
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["skipped"], 0)
        self.assertEqual(len(data["imported"]), 2)

        bookmarks = UserPageProgress.objects.get(
            user=self.user,
            page_key=PAGE_KEY,
            version=VERSION,
        )
        self.assertEqual(bookmarks.read_count, 3)
        self.assertTrue(bookmarks.is_acknowledged)
        self.assertEqual(
            set(
                UserPageSectionProgress.objects.filter(
                    user=self.user,
                    page_key=PAGE_KEY,
                    version=VERSION,
                ).values_list("section_id", flat=True)
            ),
            {"intro", "basics", "advanced"},
        )

        values = UserPageProgress.objects.get(
            user=self.user,
            page_key="alliance/values",
            version="v1",
        )
        self.assertEqual(values.read_count, 1)
        self.assertFalse(values.is_acknowledged)

    def test_import_rejects_too_many_pages(self):
        pages = [
            {
                "page_key": f"page/{i}",
                "version": "v",
                "section_total": 1,
                "read_sections": ["a"],
            }
            for i in range(MAX_IMPORT_PAGES + 1)
        ]
        r = self.client.post(
            f"{BASE}/import",
            data={"pages": pages},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 400)


class PageProgressAdminTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            password="unused",
        )
        self.progress = UserPageProgress.objects.create(
            user=self.user,
            page_key=PAGE_KEY,
            page_title="Bookmarks",
            version=VERSION,
            section_total=4,
        )
        UserPageSectionProgress.objects.create(
            user=self.user,
            page_key=PAGE_KEY,
            section_id="intro",
            version=VERSION,
        )
        UserPageSectionProgress.objects.create(
            user=self.user,
            page_key=PAGE_KEY,
            section_id="basics",
            version=VERSION,
        )

    def test_admin_progress_percent_display(self):
        admin = UserPageProgressAdmin(UserPageProgress, None)
        self.assertEqual(admin.username(self.progress), "alice")
        self.assertEqual(admin.page(self.progress), "Bookmarks")
        # 2/4 => 50%
        self.assertIn("50%", admin.progress_percent(self.progress))

    def test_admin_sections_read_on_detail(self):
        admin = UserPageProgressAdmin(UserPageProgress, None)
        html = admin.sections_read(self.progress)
        self.assertIn("intro", html)
        self.assertIn("basics", html)
        self.assertIn("2 / 4 sections", html)
