from ninja import Router

from .combatlog import (
    damage_events,
    damage_over_time,
    enemy_damage,
    parse,
    total_damage,
    weapon_damage,
    enemy_analysis,
    weapon_analysis,
    time_analysis,
    LogAnalysis,
)

router = Router(tags=["combatlog"])


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

    analysis.enemies = enemy_analysis(dmg_events)
    analysis.weapons = weapon_analysis(dmg_events)
    analysis.times = time_analysis(dmg_events)

    return analysis
