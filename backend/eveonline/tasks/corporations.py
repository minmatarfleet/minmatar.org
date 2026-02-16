import logging

from esi.models import Token

from app.celery import app

from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCorporation, EveAlliance

logger = logging.getLogger(__name__)

ALLIED_ALLIANCE_NAMES = [
    "Minmatar Fleet Alliance",
    "Minmatar Fleet Associates",
]


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.filter(
        alliance__name__in=ALLIED_ALLIANCE_NAMES
    ):
        update_corporation.apply_async(args=[corporation.corporation_id])


@app.task
def sync_alliance_corporations():
    """
    For each EveAlliance in the database, fetch corporation IDs from ESI
    (get_alliance_corporations) and get_or_create EveCorporation for each,
    then populate corporation details from ESI.
    """
    alliances = EveAlliance.objects.all().order_by("alliance_id")
    logger.info(
        "Syncing corporations for %d alliances",
        alliances.count(),
    )
    total_created = 0
    for alliance in alliances:
        esi_response = EsiClient(None).get_alliance_corporations(
            alliance.alliance_id
        )
        if not esi_response.success():
            logger.warning(
                "ESI error %d fetching corporations for alliance %s (%s)",
                esi_response.response_code,
                alliance.name or alliance.alliance_id,
                alliance.alliance_id,
            )
            continue
        corporation_ids = esi_response.results() or []
        logger.info(
            "Alliance %s (%s): %d corporations from ESI",
            alliance.name or alliance.alliance_id,
            alliance.alliance_id,
            len(corporation_ids),
        )
        for corporation_id in corporation_ids:
            corporation, created = EveCorporation.objects.get_or_create(
                corporation_id=corporation_id
            )
            if created:
                corporation.populate()
                total_created += 1
                logger.info(
                    "Created corporation %s (%s)",
                    corporation.name,
                    corporation_id,
                )
    logger.info(
        "sync_alliance_corporations complete: %d new corporations created",
        total_created,
    )
    return total_created


def _all_roles_for_member(role_data):
    """Collect all role names for a member from ESI role entry (base, hq, other)."""
    all_roles = set(role_data.get("roles") or [])
    for key in ("roles_at_base", "roles_at_hq", "roles_at_other"):
        all_roles.update(role_data.get(key) or [])
    return all_roles


@app.task
def update_corporation(corporation_id):
    logger.info("Updating corporation %s", corporation_id)
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    corporation.populate()
    if corporation.pk is None:
        return
    # fetch and set members if active (requires CEO token with membership scope)
    if corporation.active and (corporation.type in ["alliance", "associate"]):
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        if not corporation.ceo or not Token.get_token(
            corporation.ceo.character_id, required_scopes
        ):
            logger.debug(
                "Skipping member/roles sync for corporation %s (id %s): "
                "no CEO or no token with %s",
                corporation.name,
                corporation_id,
                required_scopes[0],
            )
        else:
            esi_members = EsiClient(corporation.ceo).get_corporation_members(
                corporation.corporation_id
            )
            if esi_members.success():
                for member_id in esi_members.results():
                    if not EveCharacter.objects.filter(
                        character_id=member_id
                    ).exists():
                        logger.info(
                            "Creating character %s for corporation %s",
                            member_id,
                            corporation.name,
                        )
                        EveCharacter.objects.create(character_id=member_id)

            # Populate directors, recruiters, stewards from ESI corporation roles
            esi_roles = EsiClient(corporation.ceo).get_corporation_roles(
                corporation.corporation_id
            )
            if esi_roles.success():
                roles_data = esi_roles.results() or []
                director_ids = []
                recruiter_ids = []
                steward_ids = []
                for entry in roles_data:
                    char_id = entry.get("character_id")
                    if char_id is None:
                        continue
                    all_roles = _all_roles_for_member(entry)
                    char, _ = EveCharacter.objects.get_or_create(
                        character_id=char_id, defaults={}
                    )
                    if "Director" in all_roles:
                        director_ids.append(char.id)
                    if "Personnel_Manager" in all_roles:
                        recruiter_ids.append(char.id)
                    if "Station_Manager" in all_roles:
                        steward_ids.append(char.id)
                corporation.directors.set(
                    EveCharacter.objects.filter(id__in=director_ids)
                )
                corporation.recruiters.set(
                    EveCharacter.objects.filter(id__in=recruiter_ids)
                )
                corporation.stewards.set(
                    EveCharacter.objects.filter(id__in=steward_ids)
                )
