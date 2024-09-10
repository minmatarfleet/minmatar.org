from ninja import Router
from pydantic import BaseModel
from typing import Dict

from .combatlog import (
    parse,
    damage_events,
    total_damage,
    enemy_damage,
    weapon_damage,
    damage_over_time,
)

router = Router(tags=["combatlog"])


class LogAnalysis(BaseModel):
    logged_events: int = 0
    damage_done: int = 0
    damage_taken: int = 0
    damage_from_enemies: Dict[str, int] = {}
    damage_to_enemies: Dict[str, int] = {}
    damage_with_weapons: Dict[str, int] = {}
    damage_time_in: Dict[str, int] = {}
    damage_time_out: Dict[str, int] = {}


@router.post(
    "/",
    description="Process an Eve combat log",
    response={200: LogAnalysis},
    openapi_extra={
        "requestBody": {
            "content": {"text/plain": {"schema": {"type": "string"}}}
        }
    },
)
def analyze_logs(request):
    content = request.body.decode("utf-8")

    events = parse(content)

    analysis = LogAnalysis()
    analysis.logged_events = len(events)

    dmg_events = damage_events(events)

    (analysis.damage_done, analysis.damage_taken) = total_damage(dmg_events)

    analysis.damage_from_enemies = enemy_damage(dmg_events, "from")
    analysis.damage_to_enemies = enemy_damage(dmg_events, "to")
    analysis.damage_with_weapons = weapon_damage(dmg_events)
    analysis.damage_time_in = damage_over_time(dmg_events, "from")
    analysis.damage_time_out = damage_over_time(dmg_events, "to")

    return analysis
