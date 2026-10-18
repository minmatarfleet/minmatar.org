"""Reddit access tokens are reused until near expiry."""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from reddit import oauth
from reddit.client import RedditClient

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SUBMIT_URL = "https://oauth.reddit.com/api/submit"
POST_URL = "https://www.reddit.com/r/foo/comments/x/"


def _response(status, body):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    response.text = str(body)
    return response


@override_settings(
    REDDIT_CLIENT_ID="cid",
    REDDIT_SECRET="secret",
    REDDIT_USERNAME="AllianceBot",
    REDDIT_PASSWORD="pw",
    ENV="test",
)
class RedditTokenCacheTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tokens = iter(["tok-1", "tok-2", "tok-3"])
        self.posts = []
        self.submit_status = [200]
        patcher = patch("reddit.oauth.requests.post", side_effect=self._post)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url == TOKEN_URL:
            return _response(
                200, {"access_token": next(self.tokens), "expires_in": 3600}
            )
        status = self.submit_status.pop(0)
        return _response(
            status,
            {"json": {"errors": [], "data": {"id": "x", "url": POST_URL}}},
        )

    def _token_posts(self):
        return [p for p in self.posts if p[0] == TOKEN_URL]

    def test_two_calls_make_one_token_request(self):
        client = RedditClient()
        self.assertEqual(client.get_access_token(), "tok-1")
        self.assertEqual(RedditClient().get_access_token(), "tok-1")
        self.assertEqual(len(self._token_posts()), 1)
        data = self._token_posts()[0][1]["data"]
        self.assertEqual(
            data,
            {
                "grant_type": "password",
                "username": "AllianceBot",
                "password": "pw",
            },
        )
        self.assertEqual(
            self._token_posts()[0][1]["headers"],
            {"User-Agent": "minmatar.org test"},
        )

    def test_token_is_cached_until_five_minutes_before_expiry(self):
        with patch("reddit.oauth.cache.set") as cache_set:
            RedditClient().get_access_token()
        cache_set.assert_called_once()
        self.assertEqual(cache_set.call_args.args[2], 3600 - 300)

    def test_cache_key_does_not_contain_the_credential(self):
        key = oauth._access_token_key(  # pylint: disable=protected-access
            "refresh_token", "secret-refresh"
        )
        self.assertNotIn("secret-refresh", key)

    def test_failed_grant_is_not_cached(self):
        with patch(
            "reddit.oauth.requests.post",
            return_value=_response(401, {"error": "invalid_grant"}),
        ):
            self.assertIsNone(RedditClient().get_access_token())
        self.assertEqual(RedditClient().get_access_token(), "tok-1")

    def test_submit_retries_once_with_a_fresh_token_after_401(self):
        RedditClient().get_access_token()  # warm the cache with tok-1
        self.submit_status = [401, 200]

        result = RedditClient().submit_post("foo", "title", "body")

        self.assertEqual(result, {"url": POST_URL, "id": "x"})
        submits = [p for p in self.posts if p[0] == SUBMIT_URL]
        self.assertEqual(
            [p[1]["headers"]["Authorization"] for p in submits],
            ["bearer tok-1", "bearer tok-2"],
        )
        self.assertEqual(RedditClient().get_access_token(), "tok-2")

    def test_linked_account_tokens_are_cached_per_refresh_token(self):
        account = MagicMock()
        account.refresh_token = "refresh-a"
        other = MagicMock()
        other.refresh_token = "refresh-b"
        self.assertEqual(RedditClient(account).get_access_token(), "tok-1")
        self.assertEqual(RedditClient(account).get_access_token(), "tok-1")
        self.assertEqual(RedditClient(other).get_access_token(), "tok-2")
        self.assertEqual(len(self._token_posts()), 2)
        self.assertEqual(
            self._token_posts()[0][1]["data"],
            {"grant_type": "refresh_token", "refresh_token": "refresh-a"},
        )
