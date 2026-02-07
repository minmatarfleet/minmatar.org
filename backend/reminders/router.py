import random

from ninja import Router
from pydantic import BaseModel

from reminders.messages.rat_quotes import rat_quotes

router = Router(tags=["Reminders"])


class RatQuoteResponse(BaseModel):
    quote: str


@router.get(
    "/rat-quote",
    description="Get a random quote from the Rat Bible.",
    response={200: RatQuoteResponse},
)
def get_rat_quote(request):
    quote = random.choice(rat_quotes)
    return RatQuoteResponse(quote=quote)
