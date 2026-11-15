"""Sign up for a fleet invite from a one-time link.

I'm available on the invite DM is a bot button, not a link. Discord tells
the bot who pressed it, the bot asks the API for a link (only for the
invited pilot), and replies with it so only they can see it. The link
opens a sign-up page with no login: it carries a signed token for that one
invite, and that token can only answer that invite. See
docs/fleets/invite-rsvp.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from django.core import signing
from django.db import transaction

from app.links import site_url
from fleets.helpers.composition import academy_keys, fleet_composition
from fleets.models import EveFleetInvite, EveFleetShipVolunteer

SALT = "fleets.invite-rsvp"
# The link opens for 10 minutes; a page opened in time can be sent for an
# hour, so a slow pick doesn't lose the answer.
OPEN_MAX_AGE = 10 * 60
SUBMIT_MAX_AGE = 60 * 60
CONFIDENCES = (
    EveFleetInvite.CONFIDENCE_HIGH,
    EveFleetInvite.CONFIDENCE_MEDIUM,
    EveFleetInvite.CONFIDENCE_LOW,
)


class RsvpError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# One message for a bad, expired or forwarded link: it never says which,
# and never names the fleet (a forwarded private invite leaks nothing).
EXPIRED = "This link has expired."


def mint_token(invite: EveFleetInvite) -> str:
    return signing.dumps(
        {"i": invite.id, "u": invite.user_id}, salt=SALT, compress=True
    )


def rsvp_url(token: str) -> str:
    return site_url(f"/fleets/rsvp/{token}/")


def link_for(invite: EveFleetInvite) -> str:
    """A fresh sign-up link for the invited pilot (the bot calls this
    after Discord confirms who pressed I'm available)."""
    _check_open(invite)
    return rsvp_url(mint_token(invite))


def invite_for_token(token: str, *, max_age: int) -> EveFleetInvite:
    try:
        data = signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature as exc:  # SignatureExpired included
        raise RsvpError(EXPIRED, 410) from exc
    invite = (
        EveFleetInvite.objects.select_related(
            "eve_fleet", "eve_fleet__doctrine", "user"
        )
        .filter(id=data.get("i"), user_id=data.get("u"))
        .first()
    )
    if invite is None:
        raise RsvpError(EXPIRED, 410)
    _check_open(invite)
    return invite


def _check_open(invite: EveFleetInvite) -> None:
    if invite.eve_fleet.status in ("active", "complete", "cancelled"):
        raise RsvpError("This fleet has already started.", 410)


@dataclass
class Fit:
    key: str
    name: str
    ship_id: int
    ship_name: str
    role: str
    fitting_id: int | None
    fleet_fitting_id: int | None


@dataclass
class CharacterRow:
    character_id: int
    name: str
    account: int | None
    fits: list[Fit]
    suggested_key: str = ""
    suggested_fleets: int = 0
    picked_key: str = ""
    picked: bool = False


@dataclass
class RsvpForm:
    invite: EveFleetInvite
    characters: list[CharacterRow]
    hidden_count: int
    any_ship: bool
    composition: list = field(default_factory=list)


def _key(fitting_id, fleet_fitting_id) -> str:
    return f"f:{fitting_id}" if fitting_id else f"m:{fleet_fitting_id}"


def _flyable(character_ids, fitting_ids) -> dict[int, set[int]]:
    """Catalog fits each character can fly in this fleet (capability
    engine). Characters the engine hasn't read yet are left out."""
    # pylint: disable=import-outside-toplevel
    from capabilities.models import CharacterFittingReadiness

    out: dict[int, set[int]] = {}
    for character_id, fitting_id in CharacterFittingReadiness.objects.filter(
        character__character_id__in=character_ids,
        fitting_id__in=fitting_ids,
        doctrine_ready=True,
    ).values_list("character__character_id", "fitting_id"):
        out.setdefault(character_id, set()).add(fitting_id)
    return out


def _accounts(character_ids) -> dict[int, int]:
    # pylint: disable=import-outside-toplevel
    from capabilities.models import CharacterAccountMember

    return dict(
        CharacterAccountMember.objects.filter(
            character__character_id__in=character_ids,
            account__isnull=False,
        ).values_list("character__character_id", "account__number")
    )


def build_form(invite: EveFleetInvite) -> RsvpForm:
    # pylint: disable=import-outside-toplevel
    from applications.l3arn import is_academy
    from eveonline.helpers.characters import user_characters
    from fleets.helpers.ship_suggestions import suggest_ships

    fleet = invite.eve_fleet
    user = invite.user
    characters = user_characters(user)
    character_ids = [c.character_id for c in characters]
    composition = fleet_composition(fleet)
    blocked = set() if is_academy(user) else academy_keys(composition)
    entries = [
        e
        for e in composition
        if _key(e.fitting_id, e.fleet_fitting_id) not in blocked
    ]
    fits = {
        _key(e.fitting_id, e.fleet_fitting_id): Fit(
            key=_key(e.fitting_id, e.fleet_fitting_id),
            name=e.name,
            ship_id=e.ship_id,
            ship_name=e.ship_name,
            role=e.role,
            fitting_id=e.fitting_id,
            fleet_fitting_id=None if e.fitting_id else e.fleet_fitting_id,
        )
        for e in entries
    }
    flyable = _flyable(
        character_ids, [e.fitting_id for e in entries if e.fitting_id]
    )
    accounts = _accounts(character_ids)
    suggestions = suggest_ships(fleet, character_ids, entries)
    picks = {
        v.character_id: _key(v.fitting_id, v.fleet_fitting_id)
        for v in EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=character_ids
        )
        if v.fitting_id or v.fleet_fitting_id
    }

    rows = []
    for character in characters:
        cid = character.character_id
        can = [
            f
            for f in fits.values()
            if f.fleet_fitting_id or f.fitting_id in flyable.get(cid, set())
        ]
        if fits and not can:
            continue
        suggestion = suggestions.get(cid)
        suggested = (
            _key(suggestion.fitting_id, suggestion.fleet_fitting_id)
            if suggestion
            else ""
        )
        if suggested and suggested not in {f.key for f in can}:
            suggested = ""
        rows.append(
            CharacterRow(
                character_id=cid,
                name=character.character_name,
                account=accounts.get(cid),
                fits=can,
                suggested_key=suggested,
                suggested_fleets=suggestion.fleets if suggested else 0,
                picked_key=picks.get(cid, ""),
                picked=cid in picks,
            )
        )
    if rows and not any(r.picked for r in rows):
        best = max(rows, key=lambda r: (r.suggested_fleets, -rows.index(r)))
        best.picked = True
    rows.sort(
        key=lambda r: (not r.picked, -r.suggested_fleets, r.name.lower())
    )
    return RsvpForm(
        invite=invite,
        characters=rows,
        hidden_count=len(characters) - len(rows),
        any_ship=not fits,
        composition=entries,
    )


@dataclass
class Pick:
    character_id: int
    fitting_id: int | None = None
    fleet_fitting_id: int | None = None


def submit(
    invite: EveFleetInvite, picks: list[Pick], confidence: str
) -> EveFleetInvite:
    """Sign up: replace the pilot's ships on this fleet with ``picks`` and
    record how sure they are. No picks means I'm available with no ship
    yet."""
    # pylint: disable=import-outside-toplevel
    from fleets.endpoints.fleet.put_fleet_my_ship_volunteers import (
        set_my_ship_volunteers,
    )
    from fleets.endpoints.schemas import (
        SetMyShipVolunteersRequest,
        ShipSelection,
    )
    from fleets.helpers.private_fleets import (
        PrivateFleetError,
        queue_answer_followups,
        say_in,
    )

    _check_open(invite)
    if confidence not in CONFIDENCES:
        raise RsvpError("Pick how sure you are.")
    form = build_form(invite)
    listed = {r.character_id for r in form.characters}
    selections = []
    for pick in picks:
        if pick.character_id not in listed:
            raise RsvpError("That character can't fly this fleet.")
        selections.append(
            ShipSelection(
                character_id=pick.character_id,
                fitting_id=pick.fitting_id,
                fleet_fitting_id=pick.fleet_fitting_id,
            )
        )
    picked = {p.character_id for p in picks}
    # Characters left unticked come off the fleet.
    selections += [ShipSelection(character_id=cid) for cid in listed - picked]
    with transaction.atomic():
        status, body = set_my_ship_volunteers(
            SimpleNamespace(user=invite.user),
            invite.eve_fleet_id,
            SetMyShipVolunteersRequest(selections=selections),
        )
        if status != 200:
            detail = (
                (body or {}).get("detail") if isinstance(body, dict) else None
            )
            raise RsvpError(detail or "Couldn't save your ships.", status)
        invite.refresh_from_db()
        if not picks:
            try:
                say_in(invite)
            except PrivateFleetError as exc:
                raise RsvpError(str(exc)) from exc
        invite.confidence = confidence
        invite.save(update_fields=["confidence"])
        queue_answer_followups(invite)
    return invite


def not_available(invite: EveFleetInvite) -> EveFleetInvite:
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleets import PrivateFleetError, sit_out

    _check_open(invite)
    try:
        sit_out(invite)
    except PrivateFleetError as exc:
        raise RsvpError(str(exc)) from exc
    if invite.confidence:
        invite.confidence = ""
        invite.save(update_fields=["confidence"])
    return invite
