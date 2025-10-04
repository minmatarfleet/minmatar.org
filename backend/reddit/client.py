import requests
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


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
            "https://oauth.reddit.com/api/v1/me", headers=headers
        )
        return response.json()
