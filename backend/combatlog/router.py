import io
import zipfile
import logging

from ninja import Router

from .combatlog import (
    damage_events,
    parse,
    total_damage,
    enemy_analysis,
    weapon_analysis,
    time_analysis,
    update_combat_time,
    LogAnalysis,
)

router = Router(tags=["Combat Logs"])

log = logging.getLogger(__name__)


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

    analysis = analyze_parsed_log(content)

    return analysis


def analyze_parsed_log(content: str) -> LogAnalysis:

    events = parse(content)

    analysis = LogAnalysis()
    analysis.logged_events = len(events)

    dmg_events = damage_events(events)

    (analysis.damage_done, analysis.damage_taken) = total_damage(dmg_events)

    analysis.enemies = enemy_analysis(dmg_events)
    analysis.weapons = weapon_analysis(dmg_events)
    analysis.times = time_analysis(dmg_events)

    update_combat_time(dmg_events, analysis)

    return analysis


@router.post(
    "/zipfile",
    description="Process a zipped Eve combat log",
    response={200: LogAnalysis},
    openapi_extra={
        "requestBody": {
            "content": {
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
def analyze_zipped_logs(request):
    zipdata = io.BytesIO(request.body)

    with zipfile.ZipFile(zipdata) as z:
        zip_bytes = z.read(z.infolist()[0])

    content = zip_bytes.decode("utf-8")

    return analyze_parsed_log(content)
