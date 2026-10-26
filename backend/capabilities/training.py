"""
The Training tab: what a player's characters can fly, the ship each one is
training for, and its skill plan.

Everything here reads stored rows (readiness, requirement sets, skills,
CapabilitySkill) and does light arithmetic over them; the engine itself
never runs in a request.
"""

from __future__ import annotations

import re
from collections import defaultdict

from django.db import transaction
from django.db.models import Max, Min

from capabilities.engine import plan as plan_mod
from capabilities.engine import rules
from capabilities.services import CHARACTERS_PER_ACCOUNT
from capabilities.models import (
    CapabilitySkill,
    CharacterAccount,
    CharacterAccountLink,
    CharacterAccountMember,
    CharacterCapability,
    CharacterFittingReadiness,
    CharacterShipGoal,
    CharacterTrainingSettings,
    FittingRequirementSet,
    FittingSkillRequirement,
)
from applications.l3arn import is_academy
from eveonline.models import EveCharacter, EveCharacterSkill
from fittings.models import (
    ACADEMY_ROLE,
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrineFitting,
)

# Suggestions for a character without goals: the nearest fits, if any is
# this close.
SUGGESTION_DAYS = 30
SUGGESTIONS = 2
ALSO_CLOSE = 3
# Fitting names start with the alliance tag ("[FL33T] Guardian").
NAME_TAG = re.compile(r"^\[[^\]]*\]\s*")
# Academy pilots see only a doctrine's Academy fits; everyone else never does.
# "What you can bring" columns: capitals share one.
CAPITALS = "Capitals"
COLUMN = {"Dreads": CAPITALS, "Carriers": CAPITALS}
COLUMNS = tuple(dict.fromkeys(COLUMN.get(c, c) for c in rules.CAPABILITIES))


class TrainingError(Exception):
    pass


class _Player:
    """One player's characters and the rows the views read, loaded once."""

    def __init__(self, user):
        self.user = user
        self.characters = list(
            EveCharacter.objects.filter(user=user).order_by("character_name")
        )
        pks = [c.pk for c in self.characters]
        self.levels: dict[int, dict[int, int]] = defaultdict(dict)
        self.trained_sp: dict[int, dict[int, int]] = defaultdict(dict)
        self.skill_names: dict[int, str] = {}
        for pk, skill, level, sp, name in EveCharacterSkill.objects.filter(
            character_id__in=pks
        ).values_list(
            "character_id",
            "skill_id",
            "skill_level",
            "skill_points",
            "skill_name",
        ):
            if level >= self.levels[pk].get(skill, 0):
                self.levels[pk][skill] = level
                self.trained_sp[pk][skill] = sp
            self.skill_names[skill] = name
        self.academy = is_academy(user)
        sets = {
            rs.fitting_id: rs
            for rs in FittingRequirementSet.objects.filter(
                is_current=True, fitting__deleted__isnull=True
            ).select_related("fitting")
        }
        # The doctrine places this player may see each fit in.
        self.doctrine_fits = [
            row
            for row in EveDoctrineFitting.objects.filter(
                fitting_id__in=list(sets)
            )
            .order_by("doctrine__name")
            .values(
                "fitting_id",
                "role",
                "doctrine_id",
                "doctrine__name",
                "doctrine__type",
            )
            if (row["role"] == ACADEMY_ROLE) == self.academy
        ]
        visible = {row["fitting_id"] for row in self.doctrine_fits}
        self.sets = {fid: rs for fid, rs in sets.items() if fid in visible}
        self.readiness = {
            (r.character_id, r.fitting_id): r
            for r in CharacterFittingReadiness.objects.filter(
                character_id__in=pks, fitting_id__in=list(self.sets)
            )
        }
        self.goals: dict[int, list[CharacterShipGoal]] = defaultdict(list)
        for goal in CharacterShipGoal.objects.filter(
            character_id__in=pks, fitting_id__in=list(self.sets)
        ):
            self.goals[goal.character_id].append(goal)
        self.not_for_fleets = set(
            CharacterTrainingSettings.objects.filter(
                character_id__in=pks, not_for_fleets=True
            ).values_list("character_id", flat=True)
        )
        self.doctrines: dict[int, list[str]] = defaultdict(list)
        for row in self.doctrine_fits:
            names = self.doctrines[row["fitting_id"]]
            if row["doctrine__name"] not in names:
                names.append(row["doctrine__name"])
        self.memberships = {
            m.character_id: m
            for m in CharacterAccountMember.objects.filter(
                character_id__in=pks
            ).select_related("account")
        }
        self._info = None
        self._optimal: dict[int, dict[int, int]] = {}
        self._status: dict[tuple, dict] = {}

    # ------------------------------------------------------------ lookups
    def character(self, character_id: int) -> EveCharacter:
        for c in self.characters:
            if c.character_id == character_id:
                return c
        raise TrainingError("Character not found.")

    def account_number(self, pk: int) -> int | None:
        member = self.memberships.get(pk)
        return member.account.number if member and member.account else None

    def info(self):
        if self._info is None:
            ranks, prereqs, names = {}, {}, {}
            for (
                skill_id,
                name,
                rank,
                pre,
            ) in CapabilitySkill.objects.values_list(
                "skill_id", "name", "rank", "prerequisites"
            ):
                ranks[skill_id] = rank
                names[skill_id] = name
                prereqs[skill_id] = {int(k): v for k, v in pre.items()}
            self._info = (ranks, prereqs, names)
        return self._info

    def skill_name(self, skill: int) -> str:
        return self.info()[2].get(skill) or self.skill_names.get(
            skill, f"Skill {skill}"
        )

    def optimal_targets(self, fitting_id: int) -> dict[int, int]:
        if fitting_id not in self._optimal:
            rs = self.sets[fitting_id]
            self._optimal[fitting_id] = {
                skill: max(req, fit, core, opt)
                for skill, req, fit, core, opt in FittingSkillRequirement.objects.filter(
                    requirement_set=rs
                ).values_list(
                    "skill_id",
                    "required_level",
                    "fit_level",
                    "core_level",
                    "optimal_level",
                )
            }
        return self._optimal[fitting_id]

    # ------------------------------------------------------------ plans
    def ready_targets(self, pk: int, fitting_id: int) -> dict[int, int]:
        row = self.readiness.get((pk, fitting_id))
        if row is None:
            return {}
        missing = list(row.missing_required)
        if self.sets[fitting_id].strategic:
            missing += row.missing_core
        targets: dict[int, int] = {}
        for skill, _, need in missing:
            targets[skill] = max(targets.get(skill, 0), need)
        return targets

    def steps(self, pk: int, targets: dict[int, int]):
        ranks, prereqs, _ = self.info()
        return plan_mod.plan(
            targets, self.levels[pk], ranks, prereqs, self.trained_sp[pk]
        )

    def plans(self, pk: int, fitting_id: int):
        """(steps to Ready, the further steps to Optimal)."""
        ready = self.steps(pk, self.ready_targets(pk, fitting_id))
        targets = dict(self.optimal_targets(fitting_id))
        for skill, level in self.ready_targets(pk, fitting_id).items():
            targets[skill] = max(targets.get(skill, 0), level)
        done = {(s.skill, s.level) for s in ready}
        optimal = [
            s
            for s in self.steps(pk, targets)
            if (s.skill, s.level) not in done
        ]
        return ready, optimal

    def status(self, pk: int, fitting_id: int, target: str = "ready"):
        """Ready or not, days and skills left, for one character and fit."""
        key = (pk, fitting_id, target)
        if key in self._status:
            return self._status[key]
        row = self.readiness.get((pk, fitting_id))
        ready = bool(row and row.doctrine_ready)
        steps = []
        if row is not None and not ready:
            steps = self.steps(pk, self.ready_targets(pk, fitting_id))
        if target == CharacterShipGoal.TARGET_OPTIMAL and row is not None:
            ready_steps, optimal_steps = self.plans(pk, fitting_id)
            steps = (ready_steps if not ready else []) + optimal_steps
        days = plan_mod.total_days(steps)
        if row is not None and not ready and not steps:
            days = self.estimate(pk, fitting_id)
        result = {
            "ready": ready,
            "done": not steps and ready,
            "unlocked": bool(row and row.unlocked),
            "days": days,
            "skills": len({s.skill for s in steps}),
        }
        self._status[key] = result
        return result

    def estimate(self, pk: int, fitting_id: int) -> float:
        """Stored days to Ready: cheap, for sorting many fits."""
        row = self.readiness.get((pk, fitting_id))
        if row is None:
            return float("inf")
        if row.doctrine_ready:
            return 0.0
        if self.sets[fitting_id].strategic:
            return row.days_to_core
        return row.days_to_hard

    # ------------------------------------------------------------ shapes
    def ship(self, fitting_id: int) -> dict:
        rs = self.sets[fitting_id]
        return {
            "fitting_id": fitting_id,
            "name": NAME_TAG.sub("", rs.fitting.name) or rs.fitting.name,
            "ship_type_id": rs.fitting.ship_id,
            "capability": rs.capability,
            "doctrines": self.doctrines.get(fitting_id, []),
        }

    def goal_ship(self, pk: int, goal: CharacterShipGoal) -> dict:
        return {
            **self.ship(goal.fitting_id),
            **self.status(pk, goal.fitting_id, goal.target),
            "target": goal.target,
        }

    def ready_ships(self, pk: int) -> list[dict]:
        return sorted(
            (
                self.ship(fid)
                for (c, fid), row in self.readiness.items()
                if c == pk and row.doctrine_ready
            ),
            key=lambda s: s["name"],
        )

    def nearest(self, pk: int, exclude=(), limit=SUGGESTIONS) -> list[dict]:
        candidates = sorted(
            (
                fid
                for (c, fid), row in self.readiness.items()
                if c == pk and not row.doctrine_ready and fid not in exclude
            ),
            key=lambda fid: (
                self.estimate(pk, fid),
                self.sets[fid].fitting.name,
            ),
        )
        out = []
        for fid in candidates[: limit * 2]:
            out.append({**self.ship(fid), **self.status(pk, fid)})
        out.sort(key=lambda s: (s["days"], s["name"]))
        return out[:limit]

    def summary(self, character: EveCharacter) -> dict:
        pk = character.pk
        goals = [self.goal_ship(pk, g) for g in self.goals[pk]]
        training = next((g for g in goals if not g["done"]), None)
        suggestions = []
        not_for_fleets = pk in self.not_for_fleets
        if not goals and not not_for_fleets:
            suggestions = [
                s for s in self.nearest(pk) if s["days"] <= SUGGESTION_DAYS
            ]
        return {
            "character_id": character.character_id,
            "name": character.character_name,
            "skill_points": sum(self.trained_sp[pk].values()),
            "account": self.account_number(pk),
            "not_for_fleets": not_for_fleets,
            "goals": goals,
            "goals_ready": sum(1 for g in goals if g["ready"]),
            "all_done": bool(goals) and all(g["done"] for g in goals),
            "training": training,
            "queued": [
                g["name"] for g in goals if not g["done"] and g is not training
            ],
            "ready": self.ready_ships(pk),
            "suggestions": suggestions,
            "nothing_close": not goals
            and not not_for_fleets
            and not suggestions,
        }


# ---------------------------------------------------------------- views
def overview(user) -> dict:
    player = _Player(user)
    summaries = {c.pk: player.summary(c) for c in player.characters}
    accounts: dict[int, list] = defaultdict(list)
    unplaced = []
    for c in player.characters:
        number = player.account_number(c.pk)
        if number is None:
            unplaced.append(summaries[c.pk])
        else:
            accounts[number].append(summaries[c.pk])
    return {
        "accounts": [
            {"number": number, "characters": accounts[number]}
            for number in sorted(accounts)
        ],
        "unplaced": unplaced,
        "bring": _bring(player),
    }


def _seat(player: _Player, pk: int) -> tuple:
    """One seat in a fleet: an account, or a character on no account."""
    member = player.memberships.get(pk)
    if member and member.account_id:
        return ("account", member.account_id)
    return ("character", pk)


def _pilots(player: _Player) -> list[EveCharacter]:
    return [c for c in player.characters if c.pk not in player.not_for_fleets]


def _ready_seats(player: _Player) -> dict[int, set]:
    """Per fit, the accounts (or lone characters) with someone ready in it."""
    seats: dict[int, set] = defaultdict(set)
    for (pk, fid), row in player.readiness.items():
        if row.doctrine_ready and pk not in player.not_for_fleets:
            seats[fid].add(_seat(player, pk))
    return seats


def _soonest(player: _Player, fits: list[int]) -> float | None:
    """Stored days until anyone is ready in one of these fits."""
    days = min(
        (player.estimate(c.pk, fid) for c in _pilots(player) for fid in fits),
        default=float("inf"),
    )
    return None if days == float("inf") else days


def _doctrine_fits(player: _Player) -> dict[int, dict]:
    """Each doctrine's visible fits by column, strategic doctrines first."""
    doctrines: dict[int, dict] = {}
    for row in player.doctrine_fits:
        fid = row["fitting_id"]
        doctrine = doctrines.setdefault(
            row["doctrine_id"],
            {
                "doctrine_id": row["doctrine_id"],
                "name": row["doctrine__name"],
                "strategic": row["doctrine__type"] == DOCTRINE_TYPE_STRATEGIC,
                "fits": defaultdict(list),
                "lead": None,
            },
        )
        rs = player.sets[fid]
        column = COLUMN.get(rs.capability, rs.capability)
        if fid not in doctrine["fits"][column]:
            doctrine["fits"][column].append(fid)
        if doctrine["lead"] is None and column == "DPS":
            doctrine["lead"] = fid
    return dict(
        sorted(
            doctrines.items(),
            key=lambda item: (not item[1]["strategic"], item[1]["name"]),
        )
    )


def _bring(player: _Player) -> dict:
    """Per doctrine and role: how many seats can fly it, or how soon one can.

    A seat is an account (one character flies at a time) or a character on
    no account, so the counts are how many ships the player can bring at once.
    """
    seats = _ready_seats(player)
    doctrines = _doctrine_fits(player)
    columns = [
        c for c in COLUMNS if any(d["fits"].get(c) for d in doctrines.values())
    ]
    rows = []
    for doctrine in doctrines.values():
        fits = doctrine["fits"]
        lead = doctrine["lead"] or next(iter(fits.values()))[0]
        cells = []
        doctrine_seats: set = set()
        for column in columns:
            ids = fits.get(column, [])
            ready = sum(1 for fid in ids if seats.get(fid))
            column_seats = set().union(*(seats.get(fid, set()) for fid in ids))
            doctrine_seats |= column_seats
            cells.append(
                {
                    "column": column,
                    "ships": len(ids),
                    "ready": ready,
                    "state": (
                        "none"
                        if not ids
                        else "ready" if ready == len(ids) else "needs_work"
                    ),
                    "seats": len(column_seats),
                    "days": (
                        _soonest(player, ids)
                        if ids and not column_seats
                        else None
                    ),
                }
            )
        rows.append(
            {
                "doctrine_id": doctrine["doctrine_id"],
                "name": doctrine["name"],
                "strategic": doctrine["strategic"],
                "ship_type_id": player.sets[lead].fitting.ship_id,
                "seats": len(doctrine_seats),
                "cells": cells,
            }
        )
    return {
        "academy": player.academy,
        "seats": len({_seat(player, c.pk) for c in _pilots(player)}),
        "columns": columns,
        "doctrines": rows,
    }


def doctrine_cell(user, doctrine_id: int, column: str) -> dict:
    """One doctrine's ships for one role: who flies each, or who is closest."""
    player = _Player(user)
    doctrine = _doctrine_fits(player).get(doctrine_id)
    if doctrine is None or column not in doctrine["fits"]:
        raise TrainingError("Not one of your doctrines.")
    seats = _ready_seats(player)
    pilots = _pilots(player)
    ships = []
    for fid in doctrine["fits"][column]:
        closest = None
        if not seats.get(fid):
            candidates = [c for c in pilots if (c.pk, fid) in player.readiness]
            if candidates:
                best = min(
                    candidates,
                    key=lambda c, fid=fid: (
                        player.estimate(c.pk, fid),
                        c.character_name,
                    ),
                )
                closest = {
                    "character_id": best.character_id,
                    "name": best.character_name,
                    "days": player.status(best.pk, fid)["days"],
                }
        ships.append(
            {
                **player.ship(fid),
                "accounts": len(seats.get(fid, ())),
                "closest": closest,
            }
        )
    ships.sort(key=lambda s: (s["accounts"] == 0, s["name"]))
    return {
        "doctrine_id": doctrine_id,
        "name": doctrine["name"],
        "column": column,
        "ship_type_id": player.sets[
            doctrine["lead"] or doctrine["fits"][column][0]
        ].fitting.ship_id,
        "ships": ships,
        "seats": _cell_seats(player, doctrine["fits"][column]),
    }


def _cell_seats(player: _Player, fits: list[int]) -> list[dict]:
    """One row per seat: its best character for these fits.

    That is the character ready in the most of them, else the one closest to
    being ready in one. Seats with nobody rated for any fit are left out.
    """
    by_seat: dict[tuple, list[EveCharacter]] = defaultdict(list)
    for c in _pilots(player):
        by_seat[_seat(player, c.pk)].append(c)
    rows = []
    for seat, characters in by_seat.items():
        best, ready = None, []
        for c in characters:
            flies = [
                fid
                for fid in fits
                if (row := player.readiness.get((c.pk, fid)))
                and row.doctrine_ready
            ]
            if len(flies) > len(ready):
                best, ready = c, flies
        fitting_id, days = None, 0.0
        if best is None:
            candidates = [
                (player.estimate(c.pk, fid), c.character_name, c, fid)
                for c in characters
                for fid in fits
                if (c.pk, fid) in player.readiness
            ]
            if not candidates:
                continue
            _, _, best, fitting_id = min(candidates, key=lambda x: x[:2])
            days = player.status(best.pk, fitting_id)["days"]
        rows.append(
            {
                "account": (
                    player.account_number(best.pk)
                    if seat[0] == "account"
                    else None
                ),
                "character_id": best.character_id,
                "name": best.character_name,
                "ready": bool(ready),
                "ships": [player.ship(fid)["name"] for fid in ready]
                or [player.ship(fitting_id)["name"]],
                "fitting_id": fitting_id,
                "days": days,
            }
        )
    rows.sort(
        key=lambda r: (
            not r["ready"],
            r["days"],
            r["account"] or 99,
            r["name"],
        )
    )
    return rows


def character_view(user, character_id: int) -> dict:
    player = _Player(user)
    character = player.character(character_id)
    pk = character.pk
    summary = player.summary(character)
    goal_ids = {g.fitting_id for g in player.goals[pk]}
    fleets = dict(
        CharacterCapability.objects.filter(character_id=pk).values_list(
            "capability", "fleets_365d"
        )
    )
    ready = summary["ready"]
    number = summary["account"]
    return {
        **summary,
        "account_mates": [
            c.character_name
            for c in player.characters
            if c.pk != pk
            and number is not None
            and player.account_number(c.pk) == number
        ],
        "also_close": player.nearest(pk, exclude=goal_ids, limit=ALSO_CLOSE),
        "roles": [
            {
                "capability": capability,
                "ready": [s for s in ready if s["capability"] == capability],
                "fleets_365d": fleets.get(capability, 0),
            }
            for capability in rules.CAPABILITIES
        ],
    }


def _step_rows(player: _Player, steps) -> list[dict]:
    return [
        {
            "skill_id": s.skill,
            "name": player.skill_name(s.skill),
            "level": s.level,
            "days": s.days,
        }
        for s in steps
    ]


def plan_view(user, character_id: int, fitting_id: int) -> dict:
    player = _Player(user)
    character = player.character(character_id)
    if fitting_id not in player.sets:
        raise TrainingError("Not a doctrine fit.")
    pk = character.pk
    goal = next(
        (g for g in player.goals[pk] if g.fitting_id == fitting_id), None
    )
    target = goal.target if goal else CharacterShipGoal.TARGET_READY
    ready_steps, optimal_steps = player.plans(pk, fitting_id)
    if player.status(pk, fitting_id)["ready"]:
        ready_steps = []
    queue = ready_steps + (
        optimal_steps if target == CharacterShipGoal.TARGET_OPTIMAL else []
    )
    names = {s.skill: player.skill_name(s.skill) for s in queue}
    who = []
    for c in player.characters:
        if c.pk in player.not_for_fleets and c.pk != pk:
            continue
        if (c.pk, fitting_id) not in player.readiness:
            continue
        status = player.status(c.pk, fitting_id)
        who.append(
            {
                "character_id": c.character_id,
                "name": c.character_name,
                "account": player.account_number(c.pk),
                "ready": status["ready"],
                "days": status["days"],
                "is_goal": any(
                    g.fitting_id == fitting_id for g in player.goals[c.pk]
                ),
            }
        )
    who.sort(key=lambda w: (not w["ready"], w["days"], w["name"]))
    goals = [player.goal_ship(pk, g) for g in player.goals[pk]]
    open_goals = [g for g in goals if not g["done"]]
    return {
        "ship": player.ship(fitting_id),
        "character_id": character_id,
        "name": character.character_name,
        "is_goal": goal is not None,
        "is_training": bool(
            goal and open_goals and open_goals[0]["fitting_id"] == fitting_id
        ),
        "target": target,
        "ready": player.status(pk, fitting_id)["ready"],
        "ready_steps": _step_rows(player, ready_steps),
        "ready_days": plan_mod.total_days(ready_steps),
        "optimal_steps": _step_rows(player, optimal_steps),
        "optimal_days": plan_mod.total_days(optimal_steps),
        "eve_text": plan_mod.eve_text(queue, names),
        "queue_skills": len(queue),
        "up_next": [
            g["name"] for g in open_goals if g["fitting_id"] != fitting_id
        ],
        "flown_by": [
            w["name"]
            for w in who
            if w["ready"] and w["character_id"] != character_id
        ],
        "who": who,
    }


def ship_options(user, character_id: int) -> list[dict]:
    """Doctrine fits to add, those in the most doctrines first."""
    player = _Player(user)
    pk = player.character(character_id).pk
    goal_ids = {g.fitting_id for g in player.goals[pk]}
    out = []
    for fid in player.sets:
        if (pk, fid) not in player.readiness:
            continue
        out.append(
            {
                **player.ship(fid),
                **player.status(pk, fid),
                "strategic": player.sets[fid].strategic,
                "added": fid in goal_ids,
            }
        )
    out.sort(key=lambda s: (-len(s["doctrines"]), s["days"], s["name"]))
    return out


def account_options(user, character_id: int) -> dict:
    player = _Player(user)
    character = player.character(character_id)
    pk = character.pk
    current = player.account_number(pk)
    linked: dict[int, int] = defaultdict(int)
    for a, b, n in CharacterAccountLink.objects.filter(user=user).values_list(
        "character_a_id", "character_b_id", "fleets_together"
    ):
        if a == pk:
            linked[b] += n
        elif b == pk:
            linked[a] += n
    members: dict[int, list[EveCharacter]] = defaultdict(list)
    for c in player.characters:
        number = player.account_number(c.pk)
        if number is not None and c.pk != pk:
            members[number].append(c)
    numbers = sorted(
        set(members)
        | set(
            CharacterAccount.objects.filter(user=user).values_list(
                "number", flat=True
            )
        )
    )
    return {
        "character_id": character_id,
        "name": character.character_name,
        "current": current,
        "accounts": [
            {
                "number": number,
                "characters": [c.character_name for c in members[number]],
                "size": len(members[number]),
                "full": len(members[number]) >= CHARACTERS_PER_ACCOUNT
                and number != current,
                "seen_together": sum(linked[c.pk] for c in members[number]),
                "current": number == current,
            }
            for number in numbers
        ],
    }


# ---------------------------------------------------------------- changes
def _own(user, character_id: int) -> EveCharacter:
    character = EveCharacter.objects.filter(
        user=user, character_id=character_id
    ).first()
    if character is None:
        raise TrainingError("Character not found.")
    return character


def add_goal(user, character_id: int, fitting_id: int) -> None:
    character = _own(user, character_id)
    if not FittingRequirementSet.objects.filter(
        fitting_id=fitting_id,
        is_current=True,
        fitting__deleted__isnull=True,
    ).exists():
        raise TrainingError("Not a doctrine fit.")
    last = CharacterShipGoal.objects.filter(character=character).aggregate(
        last=Max("position")
    )["last"]
    CharacterShipGoal.objects.get_or_create(
        character=character,
        fitting_id=fitting_id,
        defaults={"position": (last if last is not None else -1) + 1},
    )


def remove_goal(user, character_id: int, fitting_id: int) -> None:
    character = _own(user, character_id)
    CharacterShipGoal.objects.filter(
        character=character, fitting_id=fitting_id
    ).delete()


def update_goal(
    user,
    character_id: int,
    fitting_id: int,
    first: bool = False,
    target: str | None = None,
) -> None:
    character = _own(user, character_id)
    goal = CharacterShipGoal.objects.filter(
        character=character, fitting_id=fitting_id
    ).first()
    if goal is None:
        raise TrainingError("Not one of this character's ships.")
    if target is not None:
        if target not in dict(CharacterShipGoal.TARGET_CHOICES):
            raise TrainingError("Unknown target.")
        goal.target = target
    if first:
        lowest = CharacterShipGoal.objects.filter(
            character=character
        ).aggregate(lowest=Min("position"))["lowest"]
        goal.position = (lowest or 0) - 1
    goal.save()


def set_not_for_fleets(user, character_id: int, value: bool) -> None:
    character = _own(user, character_id)
    CharacterTrainingSettings.objects.update_or_create(
        character=character, defaults={"not_for_fleets": value}
    )


def move_character(
    user, character_id: int, account: int | None, new_account: bool = False
) -> None:
    """Put a character on an account, a new one, or none; inference keeps it."""
    character = _own(user, character_id)
    with transaction.atomic():
        if new_account:
            used = set(
                CharacterAccount.objects.filter(user=user).values_list(
                    "number", flat=True
                )
            )
            number = next(n for n in range(1, 1000) if n not in used)
            target = CharacterAccount.objects.create(
                user=user, number=number, source=CharacterAccount.SOURCE_PILOT
            )
        elif account is None:
            target = None
        else:
            target = CharacterAccount.objects.filter(
                user=user, number=account
            ).first()
            if target is None:
                raise TrainingError("Account not found.")
            others = (
                CharacterAccountMember.objects.filter(account=target)
                .exclude(character=character)
                .count()
            )
            if others >= CHARACTERS_PER_ACCOUNT:
                raise TrainingError(
                    "That account already has three characters."
                )
        CharacterAccountMember.objects.update_or_create(
            character=character,
            defaults={
                "account": target,
                "source": CharacterAccount.SOURCE_PILOT,
            },
        )
        CharacterAccount.objects.filter(
            user=user, members__isnull=True
        ).delete()
