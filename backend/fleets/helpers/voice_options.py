"""Picking a fleet's voice option when it is scheduled or edited."""

import time

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app.errors import ErrorResponse
from fleets.models import FleetVoiceOption


def resolve_fleet_voice(payload, fleet=None):
    """{voice_option, voice_channel_id, voice_channel_name, mumble_open}
    for a create (no fleet) or an update, or (400, error).

    An update that leaves the voice out keeps it. A changed option drops
    the old channel unless the request names one.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.voice_channels import resolve_voice_channel

    fields_set = getattr(payload, "model_fields_set", set())
    option_given = fleet is None or "voice_option_id" in fields_set
    if option_given and not (
        fleet is not None and payload.voice_option_id == fleet.voice_option_id
    ):
        option = resolve_voice_option(
            getattr(payload, "voice_option_id", None),
            fleet.voice_option_id if fleet else None,
        )
        if isinstance(option, tuple):
            return option
        option_changed = fleet is None or option.id != fleet.voice_option_id
    else:
        option = fleet.effective_voice_option
        option_changed = False
    result = {"voice_option": option}

    if fleet is None or "voice_channel_id" in fields_set or option_changed:
        current = None
        if fleet is not None and not option_changed and fleet.voice_channel_id:
            current = (fleet.voice_channel_id, fleet.voice_channel_name)
        channel = resolve_voice_channel(
            option, getattr(payload, "voice_channel_id", None), current
        )
        if channel and channel[0] == 400:
            return channel
        result["voice_channel_id"], result["voice_channel_name"] = channel

    mumble_open = getattr(payload, "mumble_open", None)
    if fleet is None or mumble_open is not None or option_changed:
        result["mumble_open"] = bool(
            mumble_open and option is not None and option.is_mumble
        )
    return result


def resolve_voice_option(option_id, current_id=None):
    """The option to store, or (400, error).

    No id gives the default option. An inactive option (Mumble before
    go-live) can't be picked, but a fleet that already has it keeps it.
    """
    if not option_id:
        return FleetVoiceOption.default_option()
    option = FleetVoiceOption.objects.filter(id=option_id).first()
    if option is None:
        return 400, ErrorResponse.new(f"No voice option with id {option_id}")
    if not option.is_active and option.id != current_id:
        return 400, ErrorResponse.new(f"{option.name} can't be picked yet")
    return option


# Other web workers pick up an admin change within this long.
SNAPSHOT_SECONDS = 60
_snapshot: dict | None = None


def _options() -> dict:
    """{"kinds": {id: kind}, "default": id}, reloaded after an option changes
    (in this process) or a minute (in the others), so fleet lists never
    query per fleet."""
    global _snapshot  # pylint: disable=global-statement
    now = time.monotonic()
    if _snapshot is None or now - _snapshot["at"] > SNAPSHOT_SECONDS:
        default = FleetVoiceOption.default_option()
        _snapshot = {
            "kinds": dict(FleetVoiceOption.objects.values_list("id", "kind")),
            "default": default.id if default else None,
            "at": now,
        }
    return _snapshot


@receiver([post_save, post_delete], sender=FleetVoiceOption)
def _forget_options(**kwargs):  # pylint: disable=unused-argument
    global _snapshot  # pylint: disable=global-statement
    _snapshot = None


def fleet_voice_fields(fleet) -> dict:
    options = _options()
    option_id = fleet.voice_option_id or options["default"]
    uses_mumble = (
        options["kinds"].get(option_id) == FleetVoiceOption.KIND_MUMBLE
    )
    channel_id = None if uses_mumble else fleet.voice_channel_id
    return {
        "voice_option_id": option_id,
        "uses_mumble": uses_mumble,
        "voice_channel_id": str(channel_id) if channel_id else None,
        "voice_channel_name": (
            (fleet.voice_channel_name or None) if channel_id else None
        ),
        "mumble_open": bool(uses_mumble and fleet.mumble_open),
    }
