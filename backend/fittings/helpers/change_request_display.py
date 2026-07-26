"""Human-readable HTML for doctrine and fitting change request payloads."""

import difflib

from django.utils.html import escape
from django.utils.safestring import mark_safe

from eveonline.models import EveLocation

from fittings.models import (
    DOCTRINE_TYPE_EXPERIMENTAL,
    DOCTRINE_TYPE_NON_STRATEGIC,
    DOCTRINE_TYPE_STRATEGIC,
    EVE_FITTING_VERSIONED_FIELDS,
    EveFitting,
    EveFittingChangeRequest,
    composition_snapshot_for_doctrine,
    location_ids_for_doctrine,
)

DOCTRINE_TYPE_LABELS = {
    DOCTRINE_TYPE_EXPERIMENTAL: "Experimental",
    DOCTRINE_TYPE_NON_STRATEGIC: "Non strategic",
    DOCTRINE_TYPE_STRATEGIC: "Strategic",
}

COMPOSITION_ROLE_LABELS = {
    "primary": "Primary",
    "secondary": "Secondary",
    "support": "Support",
}

FITTING_FIELD_LABELS = {
    "eft_format": "EFT",
    "description": "Description",
    "aliases": "Aliases",
    "minimum_pod": "Minimum pod",
    "recommended_pod": "Recommended pod",
    "tags": "Tags",
}

CHANGE_KIND_LABELS = {
    "full": "Full doctrine update",
    "fitting_create": "Create fitting",
    "fitting_versioned": "Fitting update",
    "fitting_delete": "Delete fitting",
    "refit_create": "Create refit",
    "refit_update": "Update refit",
    "refit_delete": "Delete refit",
}

_DIFF_PANEL_STYLE = (
    "white-space:pre-wrap;padding:0.5em;border:1px solid var(--border-color,#ddd);"
    "border-radius:4px;background:var(--darkened-bg,#f8f8f8);"
)
_DIFF_CODE_BLOCK_STYLE = (
    "font-family:ui-monospace,monospace;font-size:0.9em;"
    "border:1px solid var(--border-color,#ddd);border-radius:4px;padding:0.35em;"
    "max-height:24em;overflow:auto;background:var(--darkened-bg,#f8f8f8);"
)
_DIFF_REMOVED_STYLE = (
    "color:#f87171;background:rgba(248,113,113,0.15);padding:0.1em 0.35em;"
)
_DIFF_ADDED_STYLE = (
    "color:#4ade80;background:rgba(74,222,128,0.15);padding:0.1em 0.35em;"
)


def _doctrine_type_label(value: str) -> str:
    return DOCTRINE_TYPE_LABELS.get(value, value or "—")


def _fitting_name_map(fitting_ids: list[int]) -> dict[int, str]:
    if not fitting_ids:
        return {}
    rows = EveFitting.objects.filter(pk__in=fitting_ids).values_list(
        "pk", "name"
    )
    return dict(rows)


def _location_name_map(location_ids: list[int]) -> dict[int, str]:
    if not location_ids:
        return {}
    rows = EveLocation.objects.filter(pk__in=location_ids).values_list(
        "pk", "short_name", "location_name"
    )
    return {
        pk: (short_name or location_name or f"Location #{pk}")
        for pk, short_name, location_name in rows
    }


def _diff_value_html(current, proposed) -> str:
    current_text = escape(current if current not in (None, "") else "—")
    proposed_text = escape(proposed if proposed not in (None, "") else "—")
    if current == proposed:
        return f"<span>{proposed_text}</span>"
    return (
        f'<span style="color:#0a7;font-weight:600;">{proposed_text}</span>'
        f' <span style="color:#666;">(was {current_text})</span>'
    )


def _multiline_diff_html(current, proposed) -> str:
    current_text = current if current not in (None, "") else "—"
    proposed_text = proposed if proposed not in (None, "") else "—"
    if current_text == proposed_text:
        return (
            f'<div style="white-space:pre-wrap;margin:0;">'
            f"{escape(proposed_text)}</div>"
        )
    return (
        '<div style="display:grid;gap:0.75em;grid-template-columns:1fr 1fr;">'
        '<div><div style="font-weight:600;margin-bottom:0.25em;">Current</div>'
        f'<div style="{_DIFF_PANEL_STYLE}">{escape(current_text)}</div></div>'
        '<div><div style="font-weight:600;margin-bottom:0.25em;">Proposed</div>'
        f'<div style="{_DIFF_PANEL_STYLE}">{escape(proposed_text)}</div></div>'
        "</div>"
    )


def _eft_line_diff_html(current, proposed) -> str:
    """Line-by-line EFT diff with removed/added lines highlighted."""
    current_text = str(current or "")
    proposed_text = str(proposed or "")
    if current_text == proposed_text:
        return (
            '<pre style="white-space:pre-wrap;max-height:24em;overflow:auto;margin:0;'
            f"padding:0.5em;border:1px solid var(--border-color,#ddd);border-radius:4px;"
            f'background:var(--darkened-bg,#f8f8f8);">'
            f"{escape(proposed_text or '—')}</pre>"
        )

    current_lines = current_text.splitlines()
    proposed_lines = proposed_text.splitlines()
    diff_lines = list(difflib.Differ().compare(current_lines, proposed_lines))

    rows = []
    for line in diff_lines:
        if line.startswith("? "):
            continue
        if line.startswith("- "):
            rows.append(
                f'<div style="{_DIFF_REMOVED_STYLE}">'
                f"− {escape(line[2:])}</div>"
            )
        elif line.startswith("+ "):
            rows.append(
                f'<div style="{_DIFF_ADDED_STYLE}">'
                f"+ {escape(line[2:])}</div>"
            )
        else:
            text = line[2:] if line.startswith("  ") else line
            rows.append(
                '<div style="padding:0.1em 0.35em;">' f"{escape(text)}</div>"
            )

    return f'<div style="{_DIFF_CODE_BLOCK_STYLE}">' + "".join(rows) + "</div>"


def _composition_html(
    current_comp: dict,
    proposed_comp: dict,
    fitting_names: dict[int, str],
) -> str:
    sections = []
    for role in ("primary", "secondary", "support"):
        current_ids = set(current_comp.get(role) or [])
        proposed_ids = set(proposed_comp.get(role) or [])
        added_ids = proposed_ids - current_ids
        removed_ids = current_ids - proposed_ids
        unchanged_ids = proposed_ids & current_ids

        if not (added_ids or removed_ids or unchanged_ids):
            continue

        lines = []
        for fitting_id in sorted(unchanged_ids):
            label = fitting_names.get(fitting_id, f"Fitting #{fitting_id}")
            lines.append(f"<li>{escape(label)}</li>")
        for fitting_id in sorted(added_ids):
            label = fitting_names.get(fitting_id, f"Fitting #{fitting_id}")
            lines.append(
                f'<li><span style="color:#0a7;font-weight:600;">+ {escape(label)}</span></li>'
            )
        for fitting_id in sorted(removed_ids):
            label = fitting_names.get(fitting_id, f"Fitting #{fitting_id}")
            lines.append(
                f'<li><span style="color:#c33;font-weight:600;">− {escape(label)}</span></li>'
            )

        role_label = COMPOSITION_ROLE_LABELS[role]
        sections.append(
            f"<div style='margin-bottom:0.75em;'>"
            f"<div style='font-weight:600;margin-bottom:0.25em;'>{role_label}</div>"
            f"<ul style='margin:0 0 0 1.25em;padding:0;'>{''.join(lines)}</ul>"
            f"</div>"
        )

    if not sections:
        return (
            "<p style='margin:0;color:#666;'>No fittings in this doctrine.</p>"
        )
    return "".join(sections)


def _location_changes_html(
    current_ids: list[int],
    proposed_ids: list[int],
    location_names: dict[int, str],
) -> str:
    current_set = set(current_ids)
    proposed_set = set(proposed_ids)
    added = proposed_set - current_set
    removed = current_set - proposed_set
    unchanged = proposed_set & current_set

    if not (added or removed or unchanged):
        return "<p style='margin:0;color:#666;'>No staging locations.</p>"

    lines = []
    for location_id in sorted(unchanged):
        label = location_names.get(location_id, f"Location #{location_id}")
        lines.append(f"<li>{escape(label)}</li>")
    for location_id in sorted(added):
        label = location_names.get(location_id, f"Location #{location_id}")
        lines.append(
            f'<li><span style="color:#0a7;font-weight:600;">+ {escape(label)}</span></li>'
        )
    for location_id in sorted(removed):
        label = location_names.get(location_id, f"Location #{location_id}")
        lines.append(
            f'<li><span style="color:#c33;font-weight:600;">− {escape(label)}</span></li>'
        )
    return f"<ul style='margin:0 0 0 1.25em;padding:0;'>{''.join(lines)}</ul>"


def _composition_snapshot_html(
    composition: dict,
    fitting_names: dict[int, str],
) -> str:
    sections = []
    for role in ("primary", "secondary", "support"):
        fitting_ids = sorted(composition.get(role) or [])
        if not fitting_ids:
            continue
        lines = []
        for fitting_id in fitting_ids:
            label = fitting_names.get(fitting_id, f"Fitting #{fitting_id}")
            lines.append(f"<li>{escape(label)}</li>")
        role_label = COMPOSITION_ROLE_LABELS[role]
        sections.append(
            f"<div style='margin-bottom:0.75em;'>"
            f"<div style='font-weight:600;margin-bottom:0.25em;'>{role_label}</div>"
            f"<ul style='margin:0 0 0 1.25em;padding:0;'>{''.join(lines)}</ul>"
            f"</div>"
        )
    if not sections:
        return (
            "<p style='margin:0;color:#666;'>No fittings in this doctrine.</p>"
        )
    return "".join(sections)


def _location_list_html(
    location_ids: list[int],
    location_names: dict[int, str],
) -> str:
    if not location_ids:
        return "<p style='margin:0;color:#666;'>No staging locations.</p>"
    lines = []
    for location_id in sorted(location_ids):
        label = location_names.get(location_id, f"Location #{location_id}")
        lines.append(f"<li>{escape(label)}</li>")
    return f"<ul style='margin:0 0 0 1.25em;padding:0;'>{''.join(lines)}</ul>"


def _simple_field_html(label: str, value) -> str:
    if value in (None, ""):
        display = "—"
    elif isinstance(value, list):
        display = ", ".join(str(item) for item in value) if value else "—"
    else:
        display = str(value)
    return (
        f"<div style='margin-bottom:0.75em;'>"
        f"<div style='font-weight:600;margin-bottom:0.25em;'>{escape(label)}</div>"
        f'<div style="white-space:pre-wrap;">{escape(display)}</div>'
        f"</div>"
    )


def _eft_detail_html(eft_format: str) -> str:
    summary = _eft_summary(eft_format)
    text = str(eft_format or "")
    lines = text.splitlines()
    preview = "\n".join(lines[:10])
    if len(lines) > 10:
        preview += f"\n... ({len(lines) - 10} more lines)"
    return (
        f"<div style='margin-bottom:0.75em;'>"
        f"<div style='font-weight:600;margin-bottom:0.25em;'>EFT</div>"
        f"<div style='margin-bottom:0.35em;'>{escape(summary)}</div>"
        f'<pre style="white-space:pre-wrap;max-height:14em;overflow:auto;margin:0;'
        f"padding:0.5em;border:1px solid var(--border-color,#ddd);border-radius:4px;"
        f'background:var(--darkened-bg,#f8f8f8);">'
        f"{escape(preview)}</pre></div>"
    )


def format_doctrine_history_html(history) -> str:
    composition = history.composition or {}
    location_ids = sorted(history.location_ids or [])
    fitting_ids = set()
    for role in ("primary", "secondary", "support"):
        fitting_ids.update(composition.get(role) or [])
    fitting_names = _fitting_name_map(list(fitting_ids))
    location_names = _location_name_map(location_ids)

    rows = [
        ("Name", history.name or "—"),
        ("Type", _doctrine_type_label(history.type)),
    ]
    table_rows = []
    for label, value in rows:
        table_rows.append(
            "<tr>"
            f"<th style='text-align:left;padding:0.35em 0.75em 0.35em 0;'>"
            f"{escape(label)}</th>"
            f"<td style='padding:0.35em 0;'>{escape(value)}</td>"
            "</tr>"
        )

    return mark_safe(
        '<div class="doctrine-history-snapshot" style="max-width:960px;">'
        "<table style='width:100%;border-collapse:collapse;margin-bottom:1em;'>"
        "<tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
        + _simple_field_html("Description", history.description)
        + "<div style='font-weight:600;margin:1em 0 0.35em;'>Composition</div>"
        + _composition_snapshot_html(composition, fitting_names)
        + "<div style='font-weight:600;margin:1em 0 0.35em;'>Staging locations</div>"
        + _location_list_html(location_ids, location_names)
        + "</div>"
    )


def format_fitting_history_html(history) -> str:
    parts = [
        _simple_field_html("Name", history.name),
        _eft_detail_html(history.eft_format),
        _simple_field_html("Description", history.description),
        _simple_field_html("Aliases", history.aliases),
        _simple_field_html("Minimum pod", history.minimum_pod),
        _simple_field_html("Recommended pod", history.recommended_pod),
        _simple_field_html("Tags", _format_tags_value(history.tags)),
    ]
    return mark_safe(
        '<div class="fitting-history-snapshot" style="max-width:960px;">'
        + "".join(parts)
        + "</div>"
    )


def format_doctrine_change_request_html(change_request) -> str:
    payload = change_request.payload or {}
    doctrine = change_request.doctrine
    current_comp = composition_snapshot_for_doctrine(doctrine)
    proposed_comp = payload.get("composition") or {}
    current_location_ids = location_ids_for_doctrine(doctrine)
    proposed_location_ids = sorted(payload.get("location_ids") or [])

    fitting_ids = set()
    for comp in (current_comp, proposed_comp):
        for role in ("primary", "secondary", "support"):
            fitting_ids.update(comp.get(role) or [])
    fitting_names = _fitting_name_map(list(fitting_ids))

    all_location_ids = sorted(
        set(current_location_ids) | set(proposed_location_ids)
    )
    location_names = _location_name_map(all_location_ids)

    rows = [
        ("Name", doctrine.name, payload.get("name", "")),
        (
            "Type",
            _doctrine_type_label(doctrine.type),
            _doctrine_type_label(payload.get("type", "")),
        ),
    ]

    table_rows = []
    for label, current, proposed in rows:
        table_rows.append(
            "<tr>"
            f"<th style='text-align:left;padding:0.35em 0.75em 0.35em 0;'>"
            f"{escape(label)}</th>"
            f"<td style='padding:0.35em 0;'>{_diff_value_html(current, proposed)}</td>"
            "</tr>"
        )

    return mark_safe(
        '<div class="doctrine-change-request-review" style="max-width:960px;">'
        "<table style='width:100%;border-collapse:collapse;margin-bottom:1em;'>"
        "<tbody>" + "".join(table_rows) + "</tbody></table>"
        "<div style='font-weight:600;margin-bottom:0.35em;'>Description</div>"
        + _multiline_diff_html(
            doctrine.description, payload.get("description", "")
        )
        + "<div style='font-weight:600;margin:1em 0 0.35em;'>Composition</div>"
        + _composition_html(current_comp, proposed_comp, fitting_names)
        + "<div style='font-weight:600;margin:1em 0 0.35em;'>Staging locations</div>"
        + _location_changes_html(
            current_location_ids, proposed_location_ids, location_names
        )
        + "</div>"
    )


def _format_tags_value(value) -> str:
    if not value:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(tag) for tag in value) if value else "—"
    return str(value)


def _eft_summary(eft_format: str) -> str:
    if not eft_format or not str(eft_format).strip():
        return "—"
    ship = EveFitting.ship_name_from_eft(eft_format)
    fitting_name = EveFitting.fitting_name_from_eft(eft_format)
    line_count = len(str(eft_format).splitlines())
    return f"{ship} — {fitting_name} ({line_count} lines)"


def _fitting_field_diff_html(field: str, current, proposed) -> str:
    label = FITTING_FIELD_LABELS.get(field, field)
    if field == "eft_format":
        current_summary = _eft_summary(current)
        proposed_summary = _eft_summary(proposed)
        summary_html = (
            f"<div style='margin-bottom:0.35em;'>{escape(proposed_summary)}</div>"
            if (current or "") == (proposed or "")
            else (
                "<div style='opacity:0.75;margin-bottom:0.15em;'>"
                f"Current: {escape(current_summary)}</div>"
                "<div style='color:#4ade80;margin-bottom:0.35em;'>"
                f"Proposed: {escape(proposed_summary)}</div>"
            )
        )
        return (
            f"<div style='margin-bottom:0.75em;'>"
            f"<div style='font-weight:600;margin-bottom:0.25em;'>{escape(label)}</div>"
            f"{summary_html}"
            f"{_eft_line_diff_html(current, proposed)}"
            "</div>"
        )
    if field == "tags":
        return (
            f"<div style='margin-bottom:0.75em;'>"
            f"<div style='font-weight:600;'>{escape(label)}</div>"
            f"<div>{_diff_value_html(_format_tags_value(current), _format_tags_value(proposed))}</div>"
            "</div>"
        )
    if field in {"description", "aliases"}:
        return (
            f"<div style='margin-bottom:0.75em;'>"
            f"<div style='font-weight:600;'>{escape(label)}</div>"
            + _multiline_diff_html(current, proposed)
            + "</div>"
        )
    return (
        f"<div style='margin-bottom:0.75em;'>"
        f"<div style='font-weight:600;'>{escape(label)}</div>"
        f"<div>{_diff_value_html(current, proposed)}</div>"
        "</div>"
    )


def format_fitting_change_request_html(
    change_request: EveFittingChangeRequest,
) -> str:
    payload = change_request.payload or {}
    kind = change_request.change_kind
    kind_label = CHANGE_KIND_LABELS.get(kind, kind)

    header = (
        f'<p style="margin:0 0 1em;color:#444;">'
        f"<strong>Change type:</strong> {escape(kind_label)}"
    )
    if change_request.refit_id:
        refit_name = change_request.refit.name if change_request.refit else "—"
        header += f"<br><strong>Refit:</strong> {escape(refit_name)}"
    header += "</p>"

    if kind == "refit_delete":
        refit = change_request.refit
        refit_name = refit.name if refit else "—"
        return mark_safe(
            header + "<p style='margin:0;color:#c33;font-weight:600;'>"
            f"This request deletes refit “{escape(refit_name)}”."
            "</p>"
        )

    if kind == "fitting_delete":
        fitting_name = (
            change_request.fitting.name if change_request.fitting else "—"
        )
        return mark_safe(
            header + "<p style='margin:0;color:#c33;font-weight:600;'>"
            f"This request deletes fitting “{escape(fitting_name)}”."
            "</p>"
        )

    if kind == "fitting_create":
        field_parts = [
            (
                "<p style='margin:0 0 1em;color:#a07000;font-weight:600;'>"
                "This fitting is not live until the request is approved."
                "</p>"
            )
        ]
        for field in EVE_FITTING_VERSIONED_FIELDS:
            proposed = payload.get(field, "")
            field_parts.append(_fitting_field_diff_html(field, "", proposed))
        return mark_safe(
            header
            + '<div style="max-width:960px;">'
            + "".join(field_parts)
            + "</div>"
        )

    if kind in {"refit_create", "refit_update"}:
        current_eft = ""
        if kind == "refit_update" and change_request.refit:
            current_eft = change_request.refit.eft_format or ""
        proposed_eft = payload.get("eft_format", "")
        parts = [
            (
                "<div style='margin-bottom:0.75em;'>"
                "<div style='font-weight:600;margin-bottom:0.25em;'>Refit name</div>"
                f"<div>{escape(payload.get('name', '') or '—')}</div>"
                "</div>"
            ),
            (
                "<div style='margin-bottom:0.75em;'>"
                "<div style='font-weight:600;margin-bottom:0.25em;'>Description</div>"
                + _multiline_diff_html(
                    (
                        change_request.refit.description
                        if change_request.refit
                        else ""
                    ),
                    payload.get("description", ""),
                )
                + "</div>"
            ),
            (
                "<div style='margin-bottom:0.75em;'>"
                "<div style='font-weight:600;margin-bottom:0.25em;'>EFT</div>"
                f"<div style='margin-bottom:0.35em;'>{escape(_eft_summary(proposed_eft))}</div>"
                f"{_eft_line_diff_html(current_eft, proposed_eft)}"
                "</div>"
            ),
        ]
        return mark_safe(
            header
            + '<div style="max-width:960px;">'
            + "".join(parts)
            + "</div>"
        )

    fitting = change_request.fitting
    field_parts = []
    for field in EVE_FITTING_VERSIONED_FIELDS:
        current = getattr(fitting, field, None)
        proposed = payload.get(field, current)
        field_parts.append(_fitting_field_diff_html(field, current, proposed))

    return mark_safe(
        header
        + '<div style="max-width:960px;">'
        + "".join(field_parts)
        + "</div>"
    )
