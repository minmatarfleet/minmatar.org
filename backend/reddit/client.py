import requests
import logging

from django.conf import settings

from reddit.oauth import (
    RedditOAuthError,
    forget_access_token,
    password_access_token,
    refresh_access_token,
    user_agent,
)

logger = logging.getLogger(__name__)

EVEJOBS_SR = "/r/evejobs"
FL33T_SR = "/r/MinmatarFleet"
TEST_SR = "r/sltest1"


def normalize_subreddit(subreddit: str | None) -> str:
    """Bare subreddit name from "evejobs", "r/evejobs" or "/r/evejobs/"."""
    name = (subreddit or "").strip().strip("/")
    if name[:2].lower() == "r/":
        name = name[2:]
    return name.strip("/")


class RedditClient:
    """Client for accessing the Reddit API"""

    user_agent = "minmatar.org dev"
    client_id = ""
    client_secret = ""
    username = ""
    password = ""

    def __init__(self, account=None):
        """With a RedditAccount, act as that linked user (refresh token);
        otherwise as the alliance account (password grant)."""
        self.account = account
        self.client_id = settings.REDDIT_CLIENT_ID
        self.client_secret = settings.REDDIT_SECRET
        self.username = settings.REDDIT_USERNAME
        # Temporary hack #2 for email instead of username (?)
        self.username = (
            "BearThatCares"
            if self.username.startswith("bear")
            else self.username
        )
        self.password = settings.REDDIT_PASSWORD
        self.user_agent = user_agent()

    def get_access_token(self) -> str | None:
        """An access token, reused from the cache until near its expiry."""
        if self.account is not None:
            return self._linked_account_token()
        try:
            return password_access_token(self.username, self.password)
        except RedditOAuthError as e:
            logger.error(
                "Error getting Reddit access token for %s / %s: %s",
                self.username,
                self.client_id,
                e.code,
            )
            return None

    def forget_access_token(self) -> None:
        """Drop the cached token so the next call asks Reddit again."""
        if self.account is not None:
            if self.account.refresh_token:
                forget_access_token(
                    "refresh_token", self.account.refresh_token
                )
            return
        forget_access_token("password", self.username)

    def _authorized(self, send, url: str, **kwargs):
        """Call Reddit with the bearer token. A 401 means the cached token
        was revoked: forget it and retry once with a fresh one, which is
        what every call did before tokens were cached."""
        token = self.get_access_token()
        if not token:
            return None
        response = send(url, headers=self._headers(token), **kwargs)
        if response.status_code != 401:
            return response
        self.forget_access_token()
        token = self.get_access_token()
        if not token:
            return response
        return send(url, headers=self._headers(token), **kwargs)

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": "bearer " + token,
            "User-Agent": self.user_agent,
        }

    def _linked_account_token(self) -> str | None:
        try:
            return refresh_access_token(self.account.refresh_token)
        except RedditOAuthError as e:
            logger.warning(
                "Reddit refresh failed for %s: %s", self.account, e.code
            )
            if e.code == "invalid_grant":
                self.account.token_invalid = True
                self.account.save(update_fields=["token_invalid"])
            return None

    def get_my_details(self):
        response = self._authorized(
            requests.get, "https://oauth.reddit.com/api/v1/me", timeout=10
        )
        if response is None:
            return None
        return response.json()

    def submit_post(
        self,
        subreddit: str,
        title: str,
        content: str,
        flair_id: str | None = None,
    ) -> dict | None:
        """
        Submit a self post to a subreddit.
        Returns dict with 'url' and 'id' of the created post on success, None otherwise.
        """
        data = [
            ("kind", "self"),
            ("sr", normalize_subreddit(subreddit)),
            ("title", title),
            ("text", content),
        ]
        if flair_id:
            data.append(("flair_id", flair_id))

        response = self._authorized(
            requests.post,
            "https://oauth.reddit.com/api/submit",
            timeout=10,
            data=data,
        )
        if response is None:
            return None
        if response.status_code >= 400:
            logger.warning(
                "Submit post failed: %s (%d)", title, response.status_code
            )
            return None
        try:
            body = response.json()
            # Prefer modern response: {"json": {"errors": [], "data": {"url": "...", "id": "..."}}}
            j = body.get("json", {})
            if j.get("errors") and len(j["errors"]) > 0:
                return None
            data_obj = j.get("data", {})
            if data_obj:
                url = data_obj.get("url")
                if url and not url.startswith("http"):
                    url = "https://www.reddit.com" + url
                logger.info(
                    "Submit post: %s -> %s", title, url or data_obj.get("id")
                )
                return {"url": url, "id": data_obj.get("id")}
            # Fallback: legacy jQuery response {"success": true, "jquery": [[..., "redirect"], [..., "call", [url]]]}
            if body.get("success") and isinstance(body.get("jquery"), list):
                url = self._parse_redirect_from_jquery(body["jquery"])
                if url:
                    post_id = (
                        url.rstrip("/").split("/comments/")[-1].split("/")[0]
                    )
                    logger.info("Submit post: %s -> %s", title, url)
                    return {"url": url, "id": post_id}
        except (ValueError, KeyError, TypeError):
            pass
        logger.warning("Submit post: %s - could not parse response", title)
        return None

    @staticmethod
    def _parse_redirect_from_jquery(jquery: list) -> str | None:
        """Extract redirect URL from Reddit legacy jQuery response array."""
        for i, item in enumerate(jquery):
            if not isinstance(item, list) or len(item) < 4:
                continue
            if item[2] == "attr" and item[3] == "redirect":
                # Next entry is typically [_, _, "call", [url]]
                if i + 1 < len(jquery):
                    next_item = jquery[i + 1]
                    if (
                        isinstance(next_item, list)
                        and len(next_item) >= 4
                        and next_item[2] == "call"
                        and isinstance(next_item[3], list)
                        and len(next_item[3]) > 0
                    ):
                        url = next_item[3][0]
                        if isinstance(url, str) and "reddit.com" in url:
                            return url
        return None

    def get_link_flairs(self, subreddit: str) -> list[dict]:
        """
        Fetch link flair templates for a subreddit.
        Returns list of dicts with 'id' and 'text' (or 'name').
        """
        # Normalize: strip /r/ prefix and use lowercase (Reddit API expects lowercase)
        sr = normalize_subreddit(subreddit).lower()
        if not sr:
            return []
        response = self._authorized(
            requests.get,
            f"https://oauth.reddit.com/r/{sr}/api/link_flair",
            timeout=10,
        )
        if response is None:
            return []
        if response.status_code >= 400:
            logger.warning(
                "Link flair fetch failed for r/%s: %d %s",
                sr,
                response.status_code,
                response.text[:200],
            )
            return []
        try:
            flairs = response.json()
            result = []
            for f in flairs:
                flair_id = f.get("id") or f.get("flair_template_id")
                if flair_id is None:
                    continue
                result.append(
                    {
                        "id": str(flair_id),
                        "text": f.get("text")
                        or f.get("name")
                        or str(flair_id),
                    }
                )
            return result
        except (ValueError, KeyError, TypeError):
            return []
