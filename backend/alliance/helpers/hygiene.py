"""Trial and on-leave classification for alliance health hygiene.

Decision rules match the trial-approval and on-leave Cursor skills.
Pure functions — callers supply metrics; this module does not query the DB.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

MIN_APPROVE_DAYS = 60
RECENT_DAYS = 30

TrialDecision = Literal[
    "approve",
    "too_early",
    "fail",
    "nudge",
    "hold",
    "wrong_affiliation",
]
LeaveDecision = Literal["recommend", "keep", "exempt"]
Conf = Literal["high", "medium", "low", "—"]


def gang_bucket(size: int) -> str:
    if size <= 10:
        return "small"
    if size <= 24:
        return "medium"
    if size <= 39:
        return "large"
    return "blob"


def slice_30d(fleets_30d: int, kills_30d: int, voice_hours_30d: float) -> str:
    if fleets_30d == 0 and kills_30d == 0 and voice_hours_30d < 1:
        return "quiet"
    parts: list[str] = []
    if fleets_30d:
        parts.append(f"{fleets_30d}F")
    if kills_30d:
        parts.append(f"{kills_30d}K")
    if voice_hours_30d >= 0.1:
        parts.append(f"{voice_hours_30d}h")
    return "/".join(parts) if parts else "quiet"


def recency_ok(
    *,
    days_since_activity: Optional[int],
    fleets_30d: int,
    kills_30d: int,
    voice_hours_30d: float,
) -> bool:
    return (
        (
            days_since_activity is not None
            and days_since_activity <= RECENT_DAYS
        )
        or fleets_30d >= 1
        or kills_30d >= 1
        or voice_hours_30d >= 1
    )


def strong_paths(
    fleets: int, kills_small: int, kills: int, voice_hours: float
) -> list[str]:
    paths: list[str] = []
    if fleets >= 4:
        paths.append("Fleet")
    if kills_small >= 8:
        paths.append("Small-gang")
    if voice_hours >= 10 and (fleets >= 1 or kills >= 3):
        paths.append("Voice")
    return paths


def medium_paths(
    fleets: int, kills_small: int, kills: int, voice_hours: float
) -> list[str]:
    paths: list[str] = []
    if 2 <= fleets <= 3:
        paths.append("Fleet")
    if 4 <= kills_small <= 7:
        paths.append("Small-gang")
    if kills >= 10 and 3 <= kills_small < 8:
        paths.append("Kills")
    if 5 <= voice_hours < 10 and (fleets >= 1 or kills >= 1):
        paths.append("Voice")
    return paths


def path_label(strong: list[str], medium: list[str]) -> str:
    names = strong + [p for p in medium if p not in strong]
    if len(names) >= 2:
        return "Mixed"
    if names:
        return names[0]
    return "—"


def is_dark(fleets: int, kills: int, voice_hours: float) -> bool:
    return fleets <= 1 and kills <= 1 and voice_hours < 1


def classify_trial(
    *,
    affiliation: str = "Alliance",
    requires_trial: bool = True,
    fleets: int,
    kills: int,
    kills_small: int,
    voice_hours: float,
    fleets_30d: int,
    kills_30d: int,
    voice_hours_30d: float,
    days_since_activity: Optional[int],
    alliance_days: Optional[int],
    linked_character_count: int = 1,
) -> dict[str, Any]:
    """Classify one Alliance trial member.

    Returns decision in {approve, too_early, fail, nudge, hold, wrong_affiliation}
    plus path, conf, reason.
    """
    if affiliation != "Alliance" or not requires_trial:
        return {
            "decision": "wrong_affiliation",
            "path": "—",
            "conf": "—",
            "reason": (
                f"Wrong affiliation — {affiliation} "
                f"requires_trial={requires_trial}"
            ),
        }

    strong = strong_paths(fleets, kills_small, kills, voice_hours)
    medium = medium_paths(fleets, kills_small, kills, voice_hours)
    recent = recency_ok(
        days_since_activity=days_since_activity,
        fleets_30d=fleets_30d,
        kills_30d=kills_30d,
        voice_hours_30d=voice_hours_30d,
    )
    path = path_label(strong, medium)
    would_approve = bool(strong) or len(medium) >= 2
    too_early = alliance_days is None or alliance_days < MIN_APPROVE_DAYS

    if would_approve and recent and too_early:
        days_txt = (
            "unknown tenure"
            if alliance_days is None
            else f"{alliance_days}d in alliance"
        )
        return {
            "decision": "too_early",
            "path": path,
            "conf": "high" if strong else "medium",
            "reason": (
                f"Too early — {days_txt}; 60–90d is healthy. "
                f"On track: {fleets} fleets, {kills_small} small-gang, "
                f"{voice_hours}h (last {days_since_activity}d)."
            )[:255],
        }

    if would_approve and recent:
        conf: Conf = "high" if strong else "medium"
        return {
            "decision": "approve",
            "path": path,
            "conf": conf,
            "reason": (
                f"{path} — {fleets} fleets, {kills_small} small-gang, "
                f"{voice_hours}h voice (90d; last {days_since_activity}d)"
            )[:255],
        }

    if would_approve and not recent:
        last = days_since_activity
        last_txt = (
            "no activity in 30d"
            if last is None
            else f"last activity {last}d ago"
        )
        return {
            "decision": "nudge",
            "path": path,
            "conf": "high",
            "reason": (
                f"Front-loaded — {fleets} fleets, {kills_small} small-gang "
                f"(90d) but quiet 30d; {last_txt}."
            )[:255],
        }

    if voice_hours >= 10 and fleets == 0 and kills == 0:
        return {
            "decision": "hold",
            "path": "Voice",
            "conf": "high",
            "reason": (
                f"Voice-only social ghost — {voice_hours}h voice, "
                "no fleets or kills."
            ),
        }

    if kills >= 10 and kills_small == 0 and fleets == 0 and voice_hours < 5:
        return {
            "decision": "hold",
            "path": "—",
            "conf": "medium",
            "reason": (f"Blob-only — {kills} kills, 0 small-gang, 0 fleets."),
        }

    last = days_since_activity
    truly_dark = (
        fleets == 0
        and kills <= 1
        and voice_hours < 1
        and (last is None or last > 45)
    )
    tenure_ok_to_fail = (
        alliance_days is not None and alliance_days >= MIN_APPROVE_DAYS
    )
    if truly_dark and tenure_ok_to_fail:
        last_txt = "never in 90d" if last is None else f"last {last}d ago"
        return {
            "decision": "fail",
            "path": "—",
            "conf": "high",
            "reason": (
                f"Dark — {fleets} fleets, {kills} kills, {voice_hours}h "
                f"({alliance_days}d in alliance; {last_txt})."
            )[:255],
        }

    if is_dark(fleets, kills, voice_hours) and (
        alliance_days is not None and alliance_days < MIN_APPROVE_DAYS
    ):
        return {
            "decision": "nudge",
            "path": "—",
            "conf": "medium",
            "reason": (
                f"New trial, no first fleet — {alliance_days}d in alliance, "
                f"{fleets} fleets, {kills} kills. Walk onto a named fleet."
            )[:255],
        }

    dsa = days_since_activity
    if dsa is not None and dsa > 30:
        return {
            "decision": "nudge",
            "path": path,
            "conf": "medium",
            "reason": (
                f"Quiet on trial — {fleets} fleets, {kills_small} small-gang, "
                f"{voice_hours}h; last activity {dsa}d ago. CEO contact."
            )[:255],
        }
    if (
        dsa is not None
        and 14 <= dsa <= 30
        and (fleets >= 1 or kills >= 1 or voice_hours >= 1)
    ):
        return {
            "decision": "nudge",
            "path": path,
            "conf": "medium",
            "reason": (
                f"Fading — {fleets} fleets, {kills_small} small-gang, "
                f"{voice_hours}h; last activity {dsa}d ago. CEO contact."
            )[:255],
        }

    if linked_character_count == 0:
        return {
            "decision": "hold",
            "path": "—",
            "conf": "medium",
            "reason": "No linked characters.",
        }

    if medium:
        return {
            "decision": "hold",
            "path": path,
            "conf": "medium",
            "reason": (
                f"Hold — {fleets} fleets, {kills_small} small-gang, "
                f"{voice_hours}h; one medium path, need more."
            )[:255],
        }

    return {
        "decision": "hold",
        "path": path,
        "conf": "medium",
        "reason": (
            f"Hold — {fleets} fleets, {kills} kills ({kills_small} small), "
            f"{voice_hours}h voice; not enough participation."
        )[:255],
    }


def classify_leave(
    *,
    fleets: int,
    kills: int,
    voice_hours: float,
    linked_character_count: int = 1,
    exempt: Optional[str] = None,
    restored_from_leave_at: Optional[str] = None,
    rejoin_grace: bool = False,
) -> dict[str, Any]:
    """Classify one active Alliance member for imposed leave.

    Returns decision in {recommend, keep, exempt} plus story, conf, reason.
    Callers should only pass members with fleets < 6 (active-enough line).
    """
    if exempt:
        return {
            "decision": "exempt",
            "story": "—",
            "conf": "—",
            "reason": f"Exempt — {exempt}",
        }
    if restored_from_leave_at:
        return {
            "decision": "keep",
            "story": "Restore grace",
            "conf": "—",
            "reason": (
                f"Recent restore grace — off leave {restored_from_leave_at}."
            ),
        }
    if rejoin_grace:
        return {
            "decision": "keep",
            "story": "Rejoin grace",
            "conf": "—",
            "reason": (
                "Recent rejoin grace — first 90d fleet within 30d "
                "after a long gap."
            ),
        }
    if linked_character_count == 0:
        return {
            "decision": "recommend",
            "story": "Away",
            "conf": "medium",
            "reason": "Away — no linked characters.",
        }

    # Fleets ≥ 6 should be filtered out by the caller; treat as keep.
    if fleets >= 6:
        return {
            "decision": "keep",
            "story": "—",
            "conf": "—",
            "reason": f"Keep — {fleets} fleets (active enough).",
        }

    weak = kills < 5 and voice_hours < 5
    strong_kills = kills >= 15
    strong_voice = voice_hours >= 10

    if fleets <= 2:
        if strong_kills or strong_voice:
            conf: Conf = "medium" if strong_kills else "high"
            return {
                "decision": "recommend",
                "story": "OPSEC",
                "conf": conf,
                "reason": (
                    f"OPSEC — {fleets} fleets, {kills} kills, "
                    f"{voice_hours}h voice (90d)"
                ),
            }
        if weak:
            story = "Away" if kills <= 1 and voice_hours < 1 else "OPSEC"
            return {
                "decision": "recommend",
                "story": story,
                "conf": "high",
                "reason": (
                    f"{story} — {fleets} fleets, {kills} kills, "
                    f"{voice_hours}h voice (90d)"
                ),
            }
        return {
            "decision": "recommend",
            "story": "OPSEC",
            "conf": "high",
            "reason": (
                f"OPSEC — {fleets} fleets, {kills} kills, "
                f"{voice_hours}h voice (90d)"
            ),
        }

    # 3–5 fleets
    if kills >= 5 or voice_hours >= 5:
        return {
            "decision": "keep",
            "story": "—",
            "conf": "—",
            "reason": (
                f"Keep — {fleets} fleets with {kills} kills / "
                f"{voice_hours}h voice support."
            ),
        }
    return {
        "decision": "recommend",
        "story": "Away",
        "conf": "medium",
        "reason": (
            f"Away — {fleets} fleets on the line, {kills} kills, "
            f"{voice_hours}h voice (90d)"
        ),
    }


def sort_by_conf(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"high": 0, "medium": 1, "low": 2, "—": 3}
    return sorted(
        rows,
        key=lambda r: (
            order.get(r.get("conf", "—"), 9),
            r.get("username", ""),
        ),
    )


def build_hygiene_payload(
    trial_rows: list[dict[str, Any]],
    leave_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Group classified rows into snapshot hygiene structure."""
    trial_buckets: dict[str, list[dict[str, Any]]] = {
        "approve": [],
        "too_early": [],
        "fail": [],
        "nudge": [],
        "hold": [],
    }
    for row in trial_rows:
        decision = row.get("decision")
        if decision in trial_buckets:
            trial_buckets[decision].append(row)

    for key in trial_buckets:
        trial_buckets[key] = sort_by_conf(trial_buckets[key])

    leave_recommended = sort_by_conf(
        [r for r in leave_rows if r.get("decision") == "recommend"]
    )
    leave_kept = [r for r in leave_rows if r.get("decision") == "keep"]
    leave_exempt = [r for r in leave_rows if r.get("decision") == "exempt"]

    return {
        "trial": {
            "counts": {
                "approve": len(trial_buckets["approve"]),
                "too_early": len(trial_buckets["too_early"]),
                "fail": len(trial_buckets["fail"]),
                "nudge": len(trial_buckets["nudge"]),
                "hold": len(trial_buckets["hold"]),
            },
            "buckets": {
                "approve": trial_buckets["approve"],
                "too_early": trial_buckets["too_early"],
                "fail": trial_buckets["fail"],
                "nudge": trial_buckets["nudge"],
            },
        },
        "leave": {
            "counts": {
                "recommended": len(leave_recommended),
                "kept": len(leave_kept),
                "exempt": len(leave_exempt),
            },
            "recommended": leave_recommended,
        },
    }


def _public_trial_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "pilot": row["pilot"],
        "corp": row["corp"],
        "corporation_id": row.get("corporation_id"),
        "character_id": row.get("character_id"),
        "alliance_days": row.get("alliance_days"),
        "fleets": row["fleets"],
        "kills": row["kills"],
        "kills_small": row["kills_small"],
        "voice_hours": row["voice_hours"],
        "slice_30d": row["slice_30d"],
        "days_since_activity": row.get("days_since_activity"),
        "path": row["path"],
        "conf": row["conf"],
        "reason": row["reason"],
    }


def _public_leave_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "pilot": row["pilot"],
        "corp": row["corp"],
        "corporation_id": row.get("corporation_id"),
        "character_id": row.get("character_id"),
        "fleets": row["fleets"],
        "kills": row["kills"],
        "voice_hours": row["voice_hours"],
        "story": row["story"],
        "conf": row["conf"],
        "reason": row["reason"],
    }


def assemble_hygiene(
    *,
    trial_user_ids: set[int],
    active_user_ids: set[int],
    usernames: dict[int, str],
    display_name: dict[int, str],
    primary_corp: dict[int, int],
    primary_character: dict[int, int],
    corp_by_id: dict[int, dict[str, Any]],
    linked_character_count: dict[int, int],
    fleets_90d: dict[int, int],
    fleets_30d: dict[int, int],
    kills_90d: dict[int, int],
    kills_30d: dict[int, int],
    kills_small_90d: dict[int, int],
    voice_hours_90d: dict[int, float],
    voice_hours_30d: dict[int, float],
    days_since_activity: dict[int, Optional[int]],
    alliance_days: dict[int, Optional[int]],
    affiliation_meta: dict[int, dict[str, Any]],
    exempt_labels: dict[int, str],
    restored_from_leave_at: dict[int, Optional[str]],
    rejoin_grace: set[int],
    corp_display_name,
) -> dict[str, Any]:
    """Classify trial + leave candidates into snapshot hygiene payload."""
    trial_rows: list[dict[str, Any]] = []
    for uid in trial_user_ids:
        fleets = fleets_90d.get(uid, 0)
        kills = kills_90d.get(uid, 0)
        kills_small = kills_small_90d.get(uid, 0)
        voice = voice_hours_90d.get(uid, 0.0)
        f30 = fleets_30d.get(uid, 0)
        k30 = kills_30d.get(uid, 0)
        v30 = voice_hours_30d.get(uid, 0.0)
        dsa = days_since_activity.get(uid)
        tenure = alliance_days.get(uid)
        meta = affiliation_meta.get(
            uid, {"affiliation": "Alliance", "requires_trial": True}
        )
        cls = classify_trial(
            affiliation=meta.get("affiliation", "Alliance"),
            requires_trial=bool(meta.get("requires_trial", True)),
            fleets=fleets,
            kills=kills,
            kills_small=kills_small,
            voice_hours=voice,
            fleets_30d=f30,
            kills_30d=k30,
            voice_hours_30d=v30,
            days_since_activity=dsa,
            alliance_days=tenure,
            linked_character_count=linked_character_count.get(uid, 0),
        )
        corp_id = primary_corp.get(uid)
        corp_meta = corp_by_id.get(corp_id) if corp_id else None
        trial_rows.append(
            {
                "user_id": uid,
                "username": usernames.get(uid, str(uid)),
                "pilot": display_name.get(uid, usernames.get(uid, str(uid))),
                "corp": corp_display_name(corp_meta) if corp_meta else "—",
                "corporation_id": corp_id,
                "character_id": primary_character.get(uid),
                "alliance_days": tenure,
                "fleets": fleets,
                "kills": kills,
                "kills_small": kills_small,
                "voice_hours": voice,
                "slice_30d": slice_30d(f30, k30, v30),
                "days_since_activity": dsa,
                **cls,
            }
        )

    leave_rows: list[dict[str, Any]] = []
    for uid in active_user_ids:
        fleets = fleets_90d.get(uid, 0)
        # Soft line: only consider actives with fewer than 6 fleets.
        if fleets >= 6:
            continue
        kills = kills_90d.get(uid, 0)
        voice = voice_hours_90d.get(uid, 0.0)
        cls = classify_leave(
            fleets=fleets,
            kills=kills,
            voice_hours=voice,
            linked_character_count=linked_character_count.get(uid, 0),
            exempt=exempt_labels.get(uid),
            restored_from_leave_at=restored_from_leave_at.get(uid),
            rejoin_grace=uid in rejoin_grace,
        )
        corp_id = primary_corp.get(uid)
        corp_meta = corp_by_id.get(corp_id) if corp_id else None
        leave_rows.append(
            {
                "user_id": uid,
                "username": usernames.get(uid, str(uid)),
                "pilot": display_name.get(uid, usernames.get(uid, str(uid))),
                "corp": corp_display_name(corp_meta) if corp_meta else "—",
                "corporation_id": corp_id,
                "character_id": primary_character.get(uid),
                "fleets": fleets,
                "kills": kills,
                "voice_hours": voice,
                **cls,
            }
        )

    raw = build_hygiene_payload(trial_rows, leave_rows)
    return {
        "trial": {
            "counts": raw["trial"]["counts"],
            "buckets": {
                key: [_public_trial_row(r) for r in rows]
                for key, rows in raw["trial"]["buckets"].items()
            },
        },
        "leave": {
            "counts": raw["leave"]["counts"],
            "recommended": [
                _public_leave_row(r) for r in raw["leave"]["recommended"]
            ],
        },
    }
