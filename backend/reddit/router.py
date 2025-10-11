import logging
import requests

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer

from tech.router import permitted
from reddit.client import RedditClient

router = Router(tags=["Reddit"])
logger = logging.getLogger(__name__)


@router.get(
    "/explore",
    description="Explore Reddit API",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def poc(request, endpoint: str):
    if not permitted(request.user):
        return 403, ErrorResponse.new("Not authorised")

    reddit = RedditClient()
    token = reddit.get_access_token()

    headers = {
        "Authorization": "bearer " + token,
        "User-Agent": reddit.user_agent,
    }
    response = requests.get(
        f"https://oauth.reddit.com{endpoint}", headers=headers
    )

    logger.info(response.json())

    return 200, response.text
