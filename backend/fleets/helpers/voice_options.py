"""Picking a fleet's voice option when it is scheduled or edited."""

import time

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app.errors import ErrorResponse
from fleets.models import FleetVoiceOption


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
    return {
        "voice_option_id": option_id,
        "uses_mumble": options["kinds"].get(option_id)
        == FleetVoiceOption.KIND_MUMBLE,
    }
