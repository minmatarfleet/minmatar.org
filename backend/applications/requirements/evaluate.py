"""Check recruitment rules against people's characters, many people at once.

``evaluate(rules, user_ids)`` returns, per user, one ``Check`` per rule.
Everything is loaded in a fixed number of queries per call (not per user),
so the Settings tab can score a whole corporation.

Statuses:
  met       the rule passes
  training  a ships rule that a character is training toward (days known)
  unmet     the rule fails
  unknown   we can't tell yet (no characters, or the capability engine
            hasn't rated these ships for any of them). Never blocks.

Checks never name a character, so recruiters see pass or fail only.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Min, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from eveuniverse.models import EveType

from applications.models import CorporationRequirement as Rule
from applications.requirements import rules as R
from capabilities.models import (
    CharacterAccountMember,
    CharacterCapability,
    CharacterFittingReadiness,
)
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.models import EveCharacter, EvePlayer
from eveonline.models.characters import (
    EveCharacterCorporationHistory,
    EveCharacterKillmail,
    EveCharacterSkill,
)
from fittings.models import EveDoctrineFitting, EveFitting
from timezones.models import PilotTimezone

MET = "met"
TRAINING = "training"
UNMET = "unmet"
UNKNOWN = "unknown"

BLOCKING = frozenset({TRAINING, UNMET})
DAYS_PER_MONTH = 30.44
MAX_SHIP_ICONS = 3


@dataclass
class Check:
    rule_id: int
    kind: str
    importance: str
    text: str
    status: str
    detail: str = ""
    ship_type_ids: list[int] = field(default_factory=list)
    training_days: float | None = None

    @property
    def blocks(self) -> bool:
        return (
            self.importance == Rule.IMPORTANCE_REQUIRED
            and self.status in BLOCKING
        )

    def as_dict(self) -> dict:
        return {
            "id": self.rule_id,
            "kind": self.kind,
            "importance": self.importance,
            "text": self.text,
            "status": self.status,
            "detail": self.detail,
            "ship_type_ids": self.ship_type_ids,
            "training_days": self.training_days,
        }


def format_days(days: float) -> str:
    hours = max(1, round(days * 24))
    whole_days, rest = divmod(hours, 24)
    if whole_days and rest:
        return f"{whole_days}d {rest}h"
    if whole_days:
        return f"{whole_days}d"
    return f"{rest}h"


@dataclass
class _People:
    """Who owns which characters, and which accounts they sit on."""

    characters: dict[int, list[int]]  # user id -> character pks
    main: dict[int, int]  # user id -> main character pk
    account: dict[int, int | None]  # character pk -> account id

    def candidates(self, user_id: int, who: str) -> list[int]:
        characters = self.characters.get(user_id, [])
        main = self.main.get(user_id)
        if who == Rule.WHO_MAIN:
            return [main] if main in characters else []
        if who == Rule.WHO_OTHER_ACCOUNT:
            main_account = self.account.get(main)
            return [
                pk
                for pk in characters
                if pk != main
                and (
                    main_account is None
                    or self.account.get(pk) != main_account
                )
            ]
        return list(characters)


def _load_people(user_ids: list[int]) -> _People:
    characters: dict[int, list[int]] = defaultdict(list)
    for pk, user_id, token_user_id in EveCharacter.objects.filter(
        owned_by_q(user_ids)
    ).values_list("pk", "user_id", "token__user_id"):
        owner = user_id or token_user_id
        if owner in user_ids and pk not in characters[owner]:
            characters[owner].append(pk)
    main = dict(
        EvePlayer.objects.filter(
            user_id__in=user_ids, primary_character__isnull=False
        ).values_list("user_id", "primary_character_id")
    )
    all_pks = [pk for pks in characters.values() for pk in pks]
    account = dict(
        CharacterAccountMember.objects.filter(
            character_id__in=all_pks
        ).values_list("character_id", "account_id")
    )
    return _People(characters, main, account)


class _ShipData:
    """Readiness rows for the fittings the ships rules point at."""

    def __init__(self, rules, character_pks):
        self.doctrine_fittings: dict[int, set[int]] = defaultdict(set)
        doctrine_ids = {
            r.params.get("doctrine_id")
            for r in rules
            if r.params.get("target") == R.TARGET_DOCTRINE
        }
        for doctrine_id, fitting_id in EveDoctrineFitting.objects.filter(
            doctrine_id__in=doctrine_ids
        ).values_list("doctrine_id", "fitting_id"):
            self.doctrine_fittings[doctrine_id].add(fitting_id)
        capabilities = {
            r.params.get("capability")
            for r in rules
            if r.params.get("target") == R.TARGET_CAPABILITY
        }
        fitting_ids = set().union(*self.doctrine_fittings.values())

        # character pk -> list of (fitting id, capability, hard, doctrine,
        # days_to_hard, days_to_core)
        self.rows = defaultdict(list)
        if character_pks and (fitting_ids or capabilities):
            query = CharacterFittingReadiness.objects.filter(
                character_id__in=character_pks,
                requirement_set__is_current=True,
            )
            if capabilities and fitting_ids:
                query = query.filter(
                    Q(fitting_id__in=fitting_ids)
                    | Q(requirement_set__capability__in=capabilities)
                )
            elif capabilities:
                query = query.filter(
                    requirement_set__capability__in=capabilities
                )
            else:
                query = query.filter(fitting_id__in=fitting_ids)
            for row in query.values_list(
                "character_id",
                "fitting_id",
                "requirement_set__capability",
                "hard_ready",
                "doctrine_ready",
                "days_to_hard",
                "days_to_core",
            ):
                self.rows[row[0]].append(row[1:])
        self.proven = set()
        if character_pks and capabilities:
            self.proven = set(
                CharacterCapability.objects.filter(
                    character_id__in=character_pks,
                    capability__in=capabilities,
                    level__gte=CharacterCapability.LEVEL_PROVEN,
                ).values_list("character_id", "capability")
            )
        all_fittings = {row[0] for rows in self.rows.values() for row in rows}
        self.ship_of = {}
        fitting_names = {}
        for pk, ship_id, name in EveFitting.objects.filter(
            pk__in=all_fittings
        ).values_list("pk", "ship_id", "name"):
            self.ship_of[pk] = ship_id
            fitting_names.setdefault(ship_id, _hull_name(name))
        # The hull's name, else the fitting's without its "[TAG] " prefix.
        self.ship_names = {
            **fitting_names,
            **_type_names(set(self.ship_of.values())),
        }

    def _matcher(self, params):
        if params.get("target") == R.TARGET_CAPABILITY:
            capability = params.get("capability")
            return lambda row: row[1] == capability
        fittings = self.doctrine_fittings.get(params.get("doctrine_id"), set())
        return lambda row: row[0] in fittings

    def _scan(self, rows, doctrine_level: bool):
        """(ready ship ids, closest (days, ship) or None, any row rated)."""
        ready_ships: list[int] = []
        best_days, best_ship = None, None
        rated = False
        for fitting_id, _, hard, doctrine, days_hard, days_core in rows:
            rated = True
            ship = self.ship_of.get(fitting_id)
            if doctrine if doctrine_level else hard:
                if ship and ship not in ready_ships:
                    ready_ships.append(ship)
                continue
            days = days_core if doctrine_level else days_hard
            if days and (best_days is None or days < best_days):
                best_days, best_ship = days, ship
        best = (best_days, best_ship) if best_days is not None else None
        return ready_ships, best, rated

    def check(self, rule, candidates: list[int]) -> "_Outcome":
        params = rule.params
        level = params.get("level", R.LEVEL_CAN_FLY)
        if level == R.LEVEL_FLOWN:
            capability = params.get("capability")
            flown = any((pk, capability) in self.proven for pk in candidates)
            return _Outcome(MET if flown else UNMET)
        matches = self._matcher(params)
        rows = [
            row
            for pk in candidates
            for row in self.rows.get(pk, [])
            if matches(row)
        ]
        ready_ships, best, rated = self._scan(
            rows, level == R.LEVEL_DOCTRINE_READY
        )
        if ready_ships:
            return _Outcome(MET, ship_ids=ready_ships[:MAX_SHIP_ICONS])
        if not rated:
            return _Outcome(UNKNOWN)
        if best is None:
            return _Outcome(UNMET)
        days, ship = best
        name = self.ship_names.get(ship, "Ship")
        return _Outcome(
            TRAINING,
            f"{name} in {format_days(days)}",
            [ship] if ship else [],
            round(days, 2),
        )


def _hull_name(fitting_name: str) -> str:
    return re.sub(r"^\[[^\]]*\]\s*", "", fitting_name or "").strip()


def _type_names(type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    return dict(
        EveType.objects.filter(id__in=type_ids).values_list("id", "name")
    )


def _kill_months(character_pks, months: int) -> dict[int, set]:
    if not character_pks:
        return {}
    now = timezone.now()
    since = (now - timedelta(days=31 * months)).replace(day=1)
    result = defaultdict(set)
    rows = (
        EveCharacterKillmail.objects.filter(
            character_id__in=character_pks, killmail_time__gte=since
        )
        .annotate(month=TruncMonth("killmail_time"))
        .values_list(
            "character_id",
            "character__character_id",
            "victim_character_id",
            "month",
        )
        .distinct()
    )
    for pk, eve_id, victim, month in rows:
        if victim == eve_id:
            continue  # a loss, not a kill
        result[pk].add((month.year, month.month))
    return result


def _month_window(months: int) -> set:
    now = timezone.now()
    year, month = now.year, now.month
    window = set()
    for _ in range(months):
        window.add((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return window


@dataclass
class _Outcome:
    status: str
    detail: str = ""
    ship_ids: list[int] = field(default_factory=list)
    days: float | None = None


class _Data:
    """Everything the rules need about a set of users, loaded up front."""

    def __init__(self, rules, user_ids):
        self.people = _load_people(user_ids)
        pks = [pk for v in self.people.characters.values() for pk in v]
        kinds = {rule.kind for rule in rules}
        ship_rules = [r for r in rules if r.kind == Rule.KIND_SHIPS]
        self.ships = _ShipData(ship_rules, pks) if ship_rules else None
        months = [
            r.params["months"] for r in rules if r.kind == Rule.KIND_KILLS
        ]
        self.kill_months = _kill_months(pks, max(months)) if months else {}
        self.skill_points = (
            _skill_points(pks) if Rule.KIND_SKILL_POINTS in kinds else {}
        )
        self.born = (
            _first_seen(pks) if Rule.KIND_CHARACTER_AGE in kinds else {}
        )
        self.brackets = (
            _brackets(user_ids) if Rule.KIND_PRIME_TIME in kinds else {}
        )

    def check(self, rule, user_id) -> _Outcome:
        params = rule.params or {}
        if rule.kind == Rule.KIND_PRIME_TIME:
            mine = set(self.brackets.get(user_id) or [])
            if not mine:
                return _Outcome(UNKNOWN)
            wanted = set(params.get("brackets", []))
            return _Outcome(MET if mine & wanted else UNMET)
        candidates = self.people.candidates(user_id, rule.who)
        if not candidates:
            owns_any = bool(self.people.characters.get(user_id))
            return _Outcome(UNMET if owns_any else UNKNOWN)
        handler = {
            Rule.KIND_SHIPS: self._ships,
            Rule.KIND_KILLS: self._kills,
            Rule.KIND_SKILL_POINTS: self._skill_points,
            Rule.KIND_CHARACTER_AGE: self._age,
        }.get(rule.kind)
        return handler(rule, candidates) if handler else _Outcome(UNKNOWN)

    def _ships(self, rule, candidates):
        return self.ships.check(rule, candidates)

    def _kills(self, rule, candidates):
        params = rule.params
        window = _month_window(params["months"])
        active = set()
        for pk in candidates:
            active |= self.kill_months.get(pk, set()) & window
        count = len(active)
        return _Outcome(
            MET if count >= params["active_months"] else UNMET,
            f"{count} of {params['months']} months",
        )

    def _skill_points(self, rule, candidates):
        params = rule.params
        best = max(
            (self.skill_points.get(pk) or 0 for pk in candidates), default=0
        )
        if not best:
            return _Outcome(UNKNOWN)
        return _Outcome(
            MET if best >= params["minimum"] else UNMET,
            f"{R.format_sp(round(best, -5))} skill points",
        )

    def _age(self, rule, candidates):
        params = rule.params
        dates = [self.born[pk] for pk in candidates if self.born.get(pk)]
        if not dates:
            return _Outcome(UNKNOWN)
        cutoff = timezone.now() - timedelta(
            days=round(params["months"] * DAYS_PER_MONTH)
        )
        return _Outcome(MET if min(dates) <= cutoff else UNMET)


def _skill_points(pks) -> dict[int, int]:
    if not pks:
        return {}
    return dict(
        EveCharacterSkill.objects.filter(character_id__in=pks)
        .values("character_id")
        .annotate(total=Sum("skill_points"))
        .values_list("character_id", "total")
    )


def _first_seen(pks) -> dict:
    """Character pk -> earliest corporation history date (its birthday)."""
    if not pks:
        return {}
    return dict(
        EveCharacterCorporationHistory.objects.filter(character_id__in=pks)
        .values("character_id")
        .annotate(first=Min("start_date"))
        .values_list("character_id", "first")
    )


def _brackets(user_ids) -> dict[int, list]:
    return dict(
        PilotTimezone.objects.filter(user_id__in=user_ids).values_list(
            "user_id", "brackets"
        )
    )


def evaluate(rules, user_ids) -> dict[int, list[Check]]:
    """{user id: [Check per rule]} for each user id given."""
    rules = list(rules)
    user_ids = list({int(u) for u in user_ids})
    if not rules or not user_ids:
        return {user_id: [] for user_id in user_ids}
    names = R.doctrine_names_for(rules)
    texts = {rule.id: R.describe(rule, names) for rule in rules}
    data = _Data(rules, user_ids)
    result = {}
    for user_id in user_ids:
        checks = []
        for rule in rules:
            outcome = data.check(rule, user_id)
            checks.append(
                Check(
                    rule_id=rule.id,
                    kind=rule.kind,
                    importance=rule.importance,
                    text=texts[rule.id],
                    status=outcome.status,
                    detail=outcome.detail,
                    ship_type_ids=outcome.ship_ids,
                    training_days=outcome.days,
                )
            )
        result[user_id] = checks
    return result


def evaluate_user(rules, user_id: int) -> list[Check]:
    return evaluate(rules, [user_id]).get(user_id, [])


def blocking_checks(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.blocks]


def account_counts(user_id: int) -> tuple[int, int | None]:
    """(characters, accounts) for the 'Checked against…' line."""
    people = _load_people([user_id])
    pks = people.characters.get(user_id, [])
    accounts = [people.account.get(pk) for pk in pks]
    if not pks or None in accounts:
        return len(pks), None
    return len(pks), len(set(accounts))
