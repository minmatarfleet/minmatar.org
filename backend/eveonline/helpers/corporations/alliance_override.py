"""Corporation alliance override (BUILD -> FL33T).

A corporation with `alliance_override_from` and `alliance_override_to` set is
treated as a member of the "to" alliance while it is in the "from" alliance
in game. The override wins wherever ESI would set the alliance:

- `EveCorporation.populate` sets `corporation.alliance` to "to", so
  member/alliance corporation lists, corp type and the corp pages follow it.
  If ESI no longer has the corporation in "from", it removes the override.
- `update_character_with_affiliations` sets a member's
  `EveCharacter.alliance_id` to "to" only while ESI has them in "from", so a
  pilot who leaves the corporation, or a corporation that leaves the
  alliance, loses it on the next affiliation sync.

`apply_alliance_override` pushes an admin change through straight away
instead of waiting for the next corporation refresh and affiliation sync.
"""

import logging

from eveonline.models import EveCharacter, EveCorporation

logger = logging.getLogger(__name__)


def apply_alliance_override(corporation: EveCorporation) -> int:
    """
    Apply the corporation's alliance override (or its removal) now.

    With an override, the corporation and its members in the "from" alliance
    take the "to" alliance at once. Without one, the corporation is refreshed
    from ESI; member characters get their real alliance back on the next
    affiliation sync, which re-applies groups as for any alliance change.
    Returns the number of member characters whose alliance changed.
    """
    # pylint: disable=import-outside-toplevel
    # Imported here: eveonline.tasks and groups.tasks import eveonline.helpers.
    from eveonline.tasks import update_corporation
    from groups.tasks import update_affiliation

    source = corporation.alliance_override_from
    target = corporation.alliance_override_to
    if (
        source is None
        or target is None
        or corporation.alliance_id not in (source.id, target.id)
    ):
        # No override, or the corporation is not in the "from" alliance:
        # an ESI refresh restores its alliance (and removes the override).
        update_corporation.delay(corporation.corporation_id)
        return 0

    if corporation.alliance_id != target.id:
        corporation.alliance = target
        corporation.save(update_fields=["alliance"])

    members = EveCharacter.objects.filter(
        corporation_id=corporation.corporation_id,
        alliance_id=source.alliance_id,
    )
    user_ids = set(
        members.exclude(user__isnull=True).values_list("user_id", flat=True)
    )
    changed = members.update(alliance_id=target.alliance_id)
    logger.info(
        "Alliance override %s -> %s on corporation %s: %d characters",
        source.alliance_id,
        target.alliance_id,
        corporation.corporation_id,
        changed,
    )
    for user_id in user_ids:
        update_affiliation.delay(user_id)
    return changed
