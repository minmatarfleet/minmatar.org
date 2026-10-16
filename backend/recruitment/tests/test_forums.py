from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from recruitment.forums import (
    ForumUrlError,
    TopicNotFound,
    fetch_topic,
    in_recruitment_center,
    parse_topic_url,
)

CANONICAL = "https://forums.eveonline.com/t/rattini-tribe-is-recruiting/496493"


class ParseTopicUrlTestCase(SimpleTestCase):
    def test_canonical_url_is_kept(self):
        parsed = parse_topic_url(CANONICAL)
        self.assertEqual(CANONICAL, parsed.url)
        self.assertEqual(496493, parsed.topic_id)
        self.assertEqual("rattini-tribe-is-recruiting", parsed.slug)

    def test_post_links_and_extras_are_normalised(self):
        for url in (
            CANONICAL + "/",
            CANONICAL + "/12",
            CANONICAL + "/12/",
            CANONICAL + "?u=bear",
            CANONICAL + "/3?u=bear#post_3",
            CANONICAL + "#reply",
            "  " + CANONICAL + "  ",
            "http://forums.eveonline.com/t/rattini-tribe-is-recruiting/496493",
            "https://FORUMS.eveonline.com/t/rattini-tribe-is-recruiting/496493",
        ):
            with self.subTest(url=url):
                self.assertEqual(CANONICAL, parse_topic_url(url).url)

    def test_rejects_other_sites(self):
        for url in (
            "https://forums.eveonline.com.evil.example/t/x/1",
            "https://evil.example/t/x/496493",
            "https://www.reddit.com/t/x/496493",
            "https://forums.eveonline.com:8443/t/x/496493",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ForumUrlError) as raised:
                    parse_topic_url(url)
                self.assertEqual("not_eve_forums", raised.exception.code)

    def test_rejects_forum_pages_that_are_not_threads(self):
        for url in (
            "https://forums.eveonline.com/",
            "https://forums.eveonline.com/c/corporations-alliances/"
            "recruitment-center/63",
            "https://forums.eveonline.com/t/496493",
            "https://forums.eveonline.com/t/slug/abc",
            "https://forums.eveonline.com/t/slug/0",
            "https://forums.eveonline.com/u/bear/t/slug/1",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ForumUrlError) as raised:
                    parse_topic_url(url)
                self.assertEqual("not_a_thread", raised.exception.code)

    def test_rejects_blank_and_garbage(self):
        for url, code in (
            ("", "url_required"),
            ("   ", "url_required"),
            (None, "url_required"),
            ("forums.eveonline.com/t/x/1", "invalid_url"),
            ("javascript:alert(1)", "invalid_url"),
            ("https://[broken/t/x/1", "invalid_url"),
        ):
            with self.subTest(url=url):
                with self.assertRaises(ForumUrlError) as raised:
                    parse_topic_url(url)
                self.assertEqual(code, raised.exception.code)


def _response(status, body=None):
    response = MagicMock(status_code=status, ok=200 <= status < 300)
    response.json.return_value = body
    return response


@patch("recruitment.forums.requests.get")
class FetchTopicTestCase(SimpleTestCase):
    def test_returns_topic_json(self, get):
        get.return_value = _response(200, {"id": 1, "category_id": 63})
        self.assertEqual({"id": 1, "category_id": 63}, fetch_topic(1))
        url = get.call_args.args[0]
        self.assertEqual("https://forums.eveonline.com/t/1.json", url)
        self.assertTrue(get.call_args.kwargs["timeout"])

    def test_missing_topic(self, get):
        get.return_value = _response(404)
        with self.assertRaises(TopicNotFound):
            fetch_topic(1)

    def test_unreachable_forum_is_none(self, get):
        get.side_effect = requests.Timeout()
        self.assertIsNone(fetch_topic(1))
        get.side_effect = None
        get.return_value = _response(503)
        self.assertIsNone(fetch_topic(1))
        bad_json = _response(200)
        bad_json.json.side_effect = ValueError()
        get.return_value = bad_json
        self.assertIsNone(fetch_topic(1))


class RecruitmentCenterTestCase(SimpleTestCase):
    def test_recruitment_center(self):
        self.assertTrue(in_recruitment_center({"category_id": 63}))
        # Corporation & Alliance Discussion.
        self.assertFalse(in_recruitment_center({"category_id": 64}))
        self.assertFalse(in_recruitment_center({}))
