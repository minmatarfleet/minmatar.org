import gzip
import io
import logging
import zipfile
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer, AuthOptional
from fleets.models import EveFleet

from .combatlog import (
    LogAnalysis,
    damage_events,
    enemy_analysis,
    parse,
    time_analysis,
    total_damage,
    update_combat_time,
    weapon_analysis,
)
from .models import CombatLog

router = Router(tags=["Combat Logs"])

log = logging.getLogger(__name__)


@router.post(
    "",
    description="Process an Eve combat log",
    response={200: LogAnalysis, 400: ErrorResponse},
    auth=AuthOptional(),
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
    log.info("User = %s", str(request.user))
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
        return 400, ErrorResponse(
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
        if request.user.id:
            combat_log.created_by_id = request.user.id

        combat_log.save()

        set_ids(analysis, combat_log)

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


class LogSummary(BaseModel):
    id: int
    uploaded_at: str
    user_id: int = None
    fleet_id: int = None
    fitting_id: int = None


@router.get(
    "",
    response={200: List[LogSummary], 403: ErrorResponse},
    auth=AuthBearer(),
)
def query_saved_logs(request, user_id: int = None, fleet_id: int = None):

    if fleet_id:
        fc_id = EveFleet.objects.get(id=fleet_id).created_by_id
        is_fc = fc_id == user_id
        combat_logs = CombatLog.objects.filter(fleet_id=fleet_id)
    else:
        if request.user.id != user_id:
            return 403, ErrorResponse(
                detail="Not currently possible to see other's logs"
            )
        is_fc = False
        combat_logs = CombatLog.objects.filter(created_by_id=user_id)

    results = []
    for record in combat_logs:
        if not (record.created_by_id == user_id or is_fc):
            continue

        summary = LogSummary(
            id=record.id,
            uploaded_at=record.created_at.strftime("%m/%d/%Y, %H:%M:%S"),
        )
        if record.created_by:
            summary.user_id = record.created_by_id
        if record.fleet_id:
            summary.fleet_id = record.fleet_id
        if record.fitting_id:
            summary.fitting_id = record.fitting_id

        results.append(summary)

    return results


@router.get(
    "/{log_id}",
    response={200: LogAnalysis, 404: ErrorResponse, 403: ErrorResponse},
    auth=AuthBearer(),
)
def get_saved_log(request, log_id: int):
    try:
        db_log = CombatLog.objects.get(id=log_id)

        if db_log.created_by_id != request.user.id:
            return 403, ErrorResponse(
                detail="Not authorised to see this combat log"
            )

        analysis = analyze_parsed_log(db_log.log_text)
        analysis.db_id = log_id
        set_ids(analysis, db_log)
        return analysis
    except CombatLog.DoesNotExist:
        return 404, ErrorResponse(
            status=404,
            detail="Combat log details not found",
        )


def set_ids(analysis, db_rec):
    if db_rec.id:
        analysis.db_id = db_rec.id
    if db_rec.created_by_id:
        analysis.user_id = db_rec.created_by_id
    if db_rec.fitting_id:
        analysis.fitting_id = db_rec.fitting_id
    if db_rec.fleet_id:
        analysis.fleet_id = db_rec.fleet_id
