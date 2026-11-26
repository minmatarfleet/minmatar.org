"""Shared by the Academy graduation endpoints: find the Academy and shape
pipeline rows for the API."""

from applications import graduation
from eveonline.helpers.corporations.profile import load_corporation


def load_academy(corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None or not graduation.is_academy(corporation):
        return None
    return corporation


def review_out(review) -> dict:
    reviewer = review.reviewed_by
    return {
        "decision": review.decision,
        "corporation_ids": list(review.corporation_ids or []),
        "note": review.note,
        "reviewed_by": reviewer.username if reviewer else None,
        "created_at": review.created_at,
    }


def pilot_out(pilot, tickers: dict) -> dict:
    activity = pilot.activity
    return {
        "user_id": activity.user_id,
        "character_id": activity.character_id,
        "character_name": activity.character_name,
        "prime_time": activity.prime_time,
        "joined_at": activity.joined_at,
        "join_estimated": activity.join_estimated,
        "days_in_academy": pilot.days_in_academy,
        "skill_points": activity.skill_points,
        "fleets_90d": activity.fleets_90d,
        "fleets_30d": activity.fleets_30d,
        "kills_90d": activity.kills_90d,
        "kills_30d": activity.kills_30d,
        "small_gang_kills": activity.small_gang_kills,
        "medium_gang_kills": activity.medium_gang_kills,
        "large_gang_kills": activity.large_gang_kills,
        "voice_hours_90d": activity.voice_hours_90d,
        "ready": pilot.ready,
        "inactive": pilot.inactive,
        "stage": pilot.stage,
        "suggestions": [
            {
                "corporation_id": tickers[ticker],
                "ticker": ticker,
                "reason": reason,
            }
            for ticker, reason in pilot.suggestions
            if ticker in tickers
        ],
        "last_review": (
            review_out(pilot.last_review) if pilot.last_review else None
        ),
    }
