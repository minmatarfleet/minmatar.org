"""Counts for the fleet invite feedback round.

The comparison at the top is the whole frame: everyone asked against
everyone who submitted. Charts follow the selected cut. A cut other than
All, and either side of a split, is left out when fewer than 5 pilots
submitted. Quotes are text only, and only on All.
"""

from __future__ import annotations

from fleets.helpers.invite_feedback import (
    FELT,
    IMPROVE,
    PROBE_KEY,
    SITTING_OUT,
    WHY,
)
from fleets.models import FleetInviteFeedback, FleetInviteFeedbackRound

MIN_CELL = 5
NEW_SOURCES = {"first_week", "more_fleets"}

_SLICES = (
    ("all", "All", lambda flags: True),
    ("open", "Left one unanswered", lambda flags: flags["pending"]),
    ("answered", "Answered every one", lambda flags: not flags["pending"]),
    ("sat_out", "Sat out at least once", lambda flags: flags["sat_out"]),
    ("opened", "Opened a page", lambda flags: flags["opened"]),
    ("never_opened", "Never opened", lambda flags: not flags["opened"]),
    ("new", "New pilots", lambda flags: flags["new"]),
    ("private", "Private", lambda flags: flags["private"]),
)
_FACTS = (
    ("open", "Left an invite open", lambda flags: flags["pending"]),
    ("dose", "Got 3 or more invites", lambda flags: flags["count"] >= 3),
    ("sat_out", "Sat out at least once", lambda flags: flags["sat_out"]),
)


def results_payload(cut: str = "all", *, link_only: bool = False) -> dict:
    survey = (
        FleetInviteFeedbackRound.objects.exclude(key=PROBE_KEY)
        .order_by("-id")
        .first()
    )
    if survey is None or link_only:
        return _empty(
            show_link=survey is not None,
            status=survey.status if survey else "none",
            lede="",
        )
    rows = list(survey.responses.all())
    flagged = [(row, _flags(row)) for row in rows]
    submitted = [
        (row, flags) for row, flags in flagged if row.submitted_at is not None
    ]
    chips = _chips(submitted, cut)
    active = (
        cut
        if any(chip["key"] == cut and chip["active"] for chip in chips)
        else "all"
    )
    if active != cut:
        chips = _chips(submitted, active)
    chosen = [
        (row, flags)
        for row, flags in submitted
        if _slice_matches(active, flags)
    ]
    people = [row for row, _flags in chosen]
    payload = _empty(
        show_link=True,
        status=survey.status,
        lede=_lede(survey, len(submitted)),
    )
    payload.update(_tiles(flagged, submitted))
    payload["frame"] = _frame(flagged, submitted)
    payload["frame_note"] = _frame_note(payload["frame"])
    payload["chips"] = chips
    payload["cut"] = active
    payload["sitting_out"] = _ranked(people, "sitting_out", SITTING_OUT)
    payload["sitting_out_split"], payload["sitting_out_help"] = _answer_split(
        chosen
    )
    payload["felt"] = _ranked(people, "felt", FELT)
    payload["felt_split"], payload["felt_help"] = _dose_split(chosen)
    why_people = [row for row, flags in chosen if flags["pending"]]
    if len(why_people) >= MIN_CELL:
        payload["why"] = _ranked(why_people, "why", WHY)
        payload["why_help"] = (
            f"{len(why_people)} pilots. The form listed those fleets "
            "under the question."
        )
    payload["improve"] = _ranked_multi(people, IMPROVE)
    payload["improve_help"] = (
        "Pilots could pick two, so these counts are a priority list."
    )
    if active == "all":
        payload["quotes"] = _quotes(people)
        if payload["quotes"]:
            payload["quotes_help"] = "Only on All. No name, fleet, or date."
    return payload


def _empty(*, show_link: bool, status: str, lede: str) -> dict:
    return {
        "show_link": show_link,
        "status": status,
        "lede": lede if status != "none" else "Nothing has been sent.",
        "cohort_count": 0,
        "response_count": 0,
        "answered_percent": 0,
        "glad_or_fine_percent": 0,
        "open_replied": 0,
        "open_asked": 0,
        "frame": [],
        "frame_note": "",
        "chips": [],
        "cut": "all",
        "sitting_out": [],
        "sitting_out_split": [],
        "sitting_out_help": "",
        "felt": [],
        "felt_split": [],
        "felt_help": "",
        "why": [],
        "why_help": "",
        "improve": [],
        "improve_help": "",
        "quotes": [],
        "quotes_help": "",
    }


def _lede(survey, response_count: int) -> str:
    state = (
        "Open"
        if survey.status == FleetInviteFeedbackRound.STATUS_OPEN
        else "Closed"
    )
    return f"{state} · {response_count} answered"


def _flags(row: FleetInviteFeedback) -> dict:
    invites = row.invites or []
    return {
        "pending": any(item.get("answer") == "pending" for item in invites),
        "sat_out": any(item.get("answer") == "out" for item in invites),
        "opened": any(item.get("opened") for item in invites),
        "new": any(item.get("source_kind") in NEW_SOURCES for item in invites),
        "private": any(
            item.get("private") or item.get("invite_only") for item in invites
        ),
        "count": len(invites),
    }


def _slice_matches(cut: str, flags: dict) -> bool:
    for key, _label, test in _SLICES:
        if key == cut:
            return test(flags)
    return True


def _chips(submitted, cut: str) -> list[dict]:
    chips = []
    for key, label, test in _SLICES:
        count = sum(1 for _row, flags in submitted if test(flags))
        if key != "all" and count < MIN_CELL:
            continue
        chips.append(
            {"key": key, "label": label, "count": count, "active": key == cut}
        )
    if not any(chip["active"] for chip in chips):
        for chip in chips:
            chip["active"] = chip["key"] == "all"
    return chips


def _tiles(flagged, submitted) -> dict:
    cohort = len(flagged)
    responses = len(submitted)
    glad = sum(
        1
        for row, _flags in submitted
        if (row.answers or {}).get("felt") in {"glad", "fine"}
    )
    open_asked = sum(1 for _row, flags in flagged if flags["pending"])
    open_replied = sum(1 for _row, flags in submitted if flags["pending"])
    return {
        "cohort_count": cohort,
        "response_count": responses,
        "answered_percent": _percent(responses, cohort),
        "glad_or_fine_percent": _percent(glad, responses),
        "open_replied": open_replied,
        "open_asked": open_asked,
    }


def _frame(flagged, submitted) -> list[dict]:
    cohort = len(flagged)
    responses = len(submitted)
    rows = []
    for key, label, test in _FACTS:
        asked = sum(1 for _row, flags in flagged if test(flags))
        answered = sum(1 for _row, flags in submitted if test(flags))
        rows.append(
            {
                "key": key,
                "label": label,
                "asked_count": asked,
                "asked_percent": _percent(asked, cohort),
                "answered_count": answered,
                "answered_percent": _percent(answered, responses),
            }
        )
    return rows


def _frame_note(frame: list[dict]) -> str:
    smaller = []
    larger = []
    for row in frame:
        if row["answered_percent"] < row["asked_percent"]:
            smaller.append(_fact_phrase(row["key"]))
        elif row["answered_percent"] > row["asked_percent"]:
            larger.append(_fact_phrase(row["key"]))
    sentences = []
    if smaller:
        sentences.append(
            f"Pilots who {_join(smaller)} are a smaller share of the "
            "answers than of the people asked."
        )
    if larger:
        sentences.append(
            f"Pilots who {_join(larger)} are a larger share."
            if smaller
            else f"Pilots who {_join(larger)} are a larger share of the "
            "answers than of the people asked."
        )
    if not sentences:
        return (
            "On these three facts, the people who answered look like the "
            "people who were asked."
        )
    return " ".join(sentences)


def _fact_phrase(key: str) -> str:
    if key == "open":
        return "left an invite open"
    if key == "dose":
        return "got 3 or more"
    return "sat out at least once"


def _join(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    rest = [f"pilots who {phrase}" for phrase in phrases[1:]]
    parts = [phrases[0], *rest]
    if len(parts) == 2:
        return f"{parts[0]}, and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _answer_split(chosen):
    left = [row for row, flags in chosen if flags["pending"]]
    every = [row for row, flags in chosen if not flags["pending"]]
    sides = []
    help_bits = ["Split by the invite record."]
    left_side = _side(
        "open", "Left one open", left, "sitting_out", SITTING_OUT
    )
    every_side = _side(
        "answered", "Answered every one", every, "sitting_out", SITTING_OUT
    )
    if left_side:
        sides.append(left_side)
        help_bits.append(f"{left_side['count']} left one open.")
    if every_side:
        sides.append(every_side)
        help_bits.append(f"{every_side['count']} answered every invite.")
    return sides, " ".join(help_bits)


def _dose_split(chosen):
    one = [row for row, flags in chosen if flags["count"] == 1]
    many = [row for row, flags in chosen if flags["count"] >= 3]
    two = sum(1 for _row, flags in chosen if flags["count"] == 2)
    sides = []
    one_side = _side("one", "1 invite", one, "felt", FELT)
    many_side = _side("many", "3 or more", many, "felt", FELT)
    if one_side:
        sides.append(one_side)
    if many_side:
        sides.append(many_side)
    parts = ["By how many invites they were sent."]
    if one_side and many_side:
        parts.append("Shown for 1 invite and for 3 or more.")
    elif one_side or many_side:
        hidden = "3 or more" if one_side else "1 invite"
        parts.append(
            f"The {hidden} column is hidden: fewer than 5 pilots are in it."
        )
    if two:
        noun = "pilot" if two == 1 else "pilots"
        parts.append(
            f"The other {two} {noun} got 2 invites and stay in the "
            "bars above."
        )
    return sides, " ".join(parts)


def _side(key, label, people, question, choices):
    if len(people) < MIN_CELL:
        return None
    return {
        "key": key,
        "label": label,
        "count": len(people),
        "bars": _ordered(people, question, choices),
    }


def _ordered(people, question, choices) -> list[dict]:
    counts = _tally(people, question, choices)
    return [
        {"key": key, "label": label, "count": counts[key]}
        for key, label in choices
    ]


def _ranked(people, question, choices) -> list[dict]:
    rows = _ordered(people, question, choices)
    order = {key: index for index, (key, _label) in enumerate(choices)}
    rows.sort(key=lambda row: (-row["count"], order[row["key"]]))
    return rows


def _ranked_multi(people, choices) -> list[dict]:
    counts = {key: 0 for key, _label in choices}
    for row in people:
        for value in (row.answers or {}).get("improve") or []:
            if value in counts:
                counts[value] += 1
    rows = [
        {"key": key, "label": label, "count": counts[key]}
        for key, label in choices
    ]
    order = {key: index for index, (key, _label) in enumerate(choices)}
    rows.sort(key=lambda row: (-row["count"], order[row["key"]]))
    return rows


def _tally(people, question, choices) -> dict:
    counts = {key: 0 for key, _label in choices}
    for row in people:
        value = (row.answers or {}).get(question) or ""
        if value in counts:
            counts[value] += 1
    return counts


def _quotes(people) -> list[str]:
    ordered = sorted(
        people,
        key=lambda row: (row.submitted_at or row.created_at, row.id),
    )
    texts = []
    for row in ordered:
        answers = row.answers or {}
        for key in ("comment", "why_text"):
            text = (answers.get(key) or "").strip()
            if text:
                texts.append(text)
    return texts


def _percent(count: int, total: int) -> int:
    if not total:
        return 0
    return round(100 * count / total)
