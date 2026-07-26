"""Build admin choice lists for KnownFitting keys with assignment status."""

from fittings.known_fitting import KnownFitting
from fittings.models import ChangeRequestStatus, EveFitting


def known_fitting_admin_choices(*, exclude_pk=None):
    """
    Optgroup choices for the known_key admin field.

    Labels include the catalog key and whether another fitting already owns it,
    so editors can type-to-filter and avoid guessing which ENI/blaster key is free.
    """
    exclude_pk = exclude_pk or 0
    holders: dict[str, tuple[int, str, bool]] = {}

    for fitting_id, known_key, name in (
        EveFitting.objects.filter(known_key__isnull=False)
        .exclude(pk=exclude_pk)
        .values_list("id", "known_key", "name")
    ):
        holders[known_key] = (fitting_id, name, False)

    for fitting_id, known_key, name in (
        EveFitting.all_objects.filter(
            known_key__isnull=False,
            deleted__isnull=False,
            change_requests__status=ChangeRequestStatus.PENDING,
            change_requests__change_kind="fitting_create",
        )
        .exclude(pk=exclude_pk)
        .values_list("id", "known_key", "name")
        .distinct()
    ):
        holders.setdefault(known_key, (fitting_id, name, True))

    available: list[tuple[str, str]] = []
    in_use: list[tuple[str, str]] = []
    for value, label in KnownFitting.choices:
        display = f"{label} — {value}"
        holder = holders.get(value)
        if holder is None:
            available.append((value, f"{display} (available)"))
            continue
        fitting_id, name, pending = holder
        status = "pending create" if pending else "in use"
        in_use.append((value, f"{display} ({status}: #{fitting_id} {name})"))

    choices: list[tuple[str, list[tuple[str, str]] | str]] = [
        ("", "---------"),
    ]
    if available:
        choices.append(("Available", available))
    if in_use:
        choices.append(("Already assigned", in_use))
    return choices
