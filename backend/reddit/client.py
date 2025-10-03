import requests

from django.conf import settings


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

    def get_access_token(self) -> str:
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
        return response.json()["access_token"]

    def get_my_details(self):
        headers = {
            "Authorization": "bearer " + self.get_access_token(),
            "User-Agent": self.user_agent,
        }
        response = requests.get(
            "https://oauth.reddit.com/api/v1/me", headers=headers
        )
        return response.json()
