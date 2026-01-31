import requests
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

EVEJOBS_SR = "/r/evejobs"
FL33T_SR = "/r/MinmatarFleet"
TEST_SR = "r/sltest1"


class RedditClient:
    """Client for accessing the Reddit API"""

    user_agent = "minmatar.org dev"
    client_id = ""
    client_secret = ""
    username = ""
    password = ""

    def __init__(self):
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
        self.user_agent = "minmatar.org " + settings.ENV

    def get_access_token(self) -> str | None:
        logger.info(
            "Getting reddit access token for %s / %s",
            self.username,
            self.client_id,
        )
        client_auth = requests.auth.HTTPBasicAuth(
            self.client_id, self.client_secret
        )
        post_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        headers = {"User-Agent": self.user_agent}
        response = requests.post(
            url="https://www.reddit.com/api/v1/access_token",
            timeout=10,
            auth=client_auth,
            headers=headers,
            data=post_data,
        )
        if response.status_code >= 400:
            logger.error(
                "Error %d getting Reddit access token: %s",
                response.status_code,
                response.text,
            )
            return None
        data = response.json()
        if "access_token" in data:
            return data["access_token"]
        else:
            logger.error("No access token found in %s", data)
            return None

    def get_my_details(self):
        token = self.get_access_token()
        if not token:
            return
        headers = {
            "Authorization": "bearer " + token,
            "User-Agent": self.user_agent,
        }
        response = requests.get(
            "https://oauth.reddit.com/api/v1/me",
            headers=headers,
            timeout=10,
        )
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
        token = self.get_access_token()
        if not token:
            return None

        data = [
            ("kind", "self"),
            ("sr", subreddit.lstrip("/r")),
            ("title", title),
            ("text", content),
        ]
        if flair_id:
            data.append(("flair_id", flair_id))

        response = requests.post(
            url="https://oauth.reddit.com/api/submit",
            headers={
                "Authorization": "bearer " + token,
                "User-Agent": self.user_agent,
            },
            timeout=10,
            data=data,
        )
        if response.status_code >= 400:
            logger.warning("Submit post failed: %s (%d)", title, response.status_code)
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
                logger.info("Submit post: %s -> %s", title, url or data_obj.get("id"))
                return {"url": url, "id": data_obj.get("id")}
            # Fallback: legacy jQuery response {"success": true, "jquery": [[..., "redirect"], [..., "call", [url]]]}
            if body.get("success") and isinstance(body.get("jquery"), list):
                url = self._parse_redirect_from_jquery(body["jquery"])
                if url:
                    post_id = url.rstrip("/").split("/comments/")[-1].split("/")[0]
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
        token = self.get_access_token()
        if not token:
            return []
        # Normalize: strip /r/ prefix and use lowercase (Reddit API expects lowercase)
        sr = (subreddit or "").strip().lstrip("/").lstrip("r").lstrip("/").strip().lower()
        if not sr:
            return []
        response = requests.get(
            url=f"https://oauth.reddit.com/r/{sr}/api/link_flair",
            headers={
                "Authorization": "bearer " + token,
                "User-Agent": self.user_agent,
            },
            timeout=10,
        )
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
                        "text": f.get("text") or f.get("name") or str(flair_id),
                    }
                )
            return result
        except (ValueError, KeyError, TypeError):
            return []