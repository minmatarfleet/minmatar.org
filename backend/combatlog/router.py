import io
import zipfile
import gzip
import logging

from ninja import Router

from app.errors import ErrorResponse

from .models import CombatLog

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
    "",
    description="Process an Eve combat log",
    response={200: LogAnalysis, 400: ErrorResponse},
    openapi_extra={
        "requestBody": {
            "content": {
                "text/plain": {"schema": {"type": "string"}},
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"}
                },
                "application/gzip": {
                    "schema": {"type": "string", "format": "binary"}
                },
            },
        },
    },
)
def analyze_logs(
    request,
    fleet_id: int = 0,
    fitting_id: int = 0,
    start_time: str = "",
    end_time: str = "",
):
    log.info("Combat log fleet ID = %d, fitting ID = %d", fleet_id, fitting_id)
    log.info("Combat log time range = %s to %s", start_time, end_time)

    if request.content_type == "text/plain":
        content = request.body.decode("utf-8")
    elif request.content_type == "application/zip":
        zipdata = io.BytesIO(request.body)
        with zipfile.ZipFile(zipdata) as z:
            zip_bytes = z.read(z.infolist()[0])
        content = zip_bytes.decode("utf-8")
    elif request.content_type == "application/gzip":
        zipdata = io.BytesIO(request.body)
        gzip_bytes = gzip.decompress(zipdata.read())
        content = gzip_bytes.decode("utf-8")
    else:
        return ErrorResponse(
            status=400,
            detail="Content type not supported: " + request.content_type,
        )

    analysis = analyze_parsed_log(content)

    if fleet_id > 0 or fitting_id > 0:
        combat_log = CombatLog(log_text=content)
        if fleet_id > 0:
            combat_log.fleet_id = fleet_id
        if fitting_id > 0:
            combat_log.fitting_id = fitting_id
        combat_log.save()
        analysis.db_id = combat_log.id

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


@router.get("/{id}", response={200: LogAnalysis})
def get_saved_log(request, id: int):
    db_log = CombatLog.objects.get(id=id)
    analysis = analyze_parsed_log(db_log.log_text)
    return analysis
