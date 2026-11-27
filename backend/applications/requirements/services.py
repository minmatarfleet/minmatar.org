"""Recruitment requirements: reading, editing, scoring and the apply gate."""

import hashlib
import json
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from applications.models import CorporationRequirement as Rule
from applications.requirements import rules as R
from applications.requirements.evaluate import (
    blocking_checks,
    evaluate,
    evaluate_user,
)
from eveonline.character_sync import SKILLS
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.helpers.corporations.profile import split_requirements
from eveonline.models import (
    EveCharacter,
    EveCharacterSyncState,
    EveCorporation,
    EvePlayer,
)

logger = logging.getLogger(__name__)

PASS_RATE_TTL = 6 * 60 * 60
# An applicant blocked by a rule gets a skills sync for characters whose
# skills are older than this; applicants outside the alliance are not on
# the regular sync schedule, so theirs can be weeks old.
SKILLS_STALE_AFTER = timedelta(hours=6)
SKILLS_REFRESH_COOLDOWN = 60 * 60
SKILLS_REFRESH_KEY = "applications:skills_refresh"
MAX_TOPICS = 12
MAX_TOPIC_LENGTH = 200


def corporation_rules(corporation: EveCorporation) -> list[Rule]:
    return list(Rule.objects.filter(corporation=corporation))


def interview_topics(corporation: EveCorporation) -> list[str]:
    """The corp's free-text requirement lines, without list markers."""
    topics = []
    for line in split_requirements(corporation.requirements):
        topic = line.lstrip("-*• ").strip()
        if topic:
            topics.append(topic)
    return topics


def save_interview_topics(corporation: EveCorporation, topics: list[str]):
    cleaned = []
    for topic in topics:
        topic = " ".join((topic or "").split())[:MAX_TOPIC_LENGTH]
        if topic and topic not in cleaned:
            cleaned.append(topic)
    corporation.requirements = "\n".join(
        f"- {t}" for t in cleaned[:MAX_TOPICS]
    )
    corporation.save(update_fields=["requirements"])


def rule_dict(rule: Rule, names: dict | None = None) -> dict:
    return {
        "id": rule.id,
        "kind": rule.kind,
        "params": rule.params or {},
        "who": rule.who,
        "importance": rule.importance,
        "position": rule.position,
        "text": R.describe(rule, names or {}),
    }


def rule_dicts(rules: list[Rule]) -> list[dict]:
    names = R.doctrine_names_for(rules)
    return [rule_dict(rule, names) for rule in rules]


def create_rule(corporation, user, kind, params, who, importance) -> Rule:
    clean = R.clean_rule(kind, params, who, importance)
    with transaction.atomic():
        existing = Rule.objects.select_for_update().filter(
            corporation=corporation
        )
        if existing.count() >= R.MAX_RULES_PER_CORPORATION:
            raise R.RuleError(
                f"A corporation can have up to {R.MAX_RULES_PER_CORPORATION} "
                "requirements"
            )
        last = existing.order_by("-position").first()
        return Rule.objects.create(
            corporation=corporation,
            kind=clean.kind,
            params=clean.params,
            who=clean.who,
            importance=clean.importance,
            position=(last.position + 1) if last else 0,
            created_by=user,
        )


def update_rule(rule: Rule, *, params=None, who=None, importance=None) -> Rule:
    clean = R.clean_rule(
        rule.kind,
        rule.params if params is None else params,
        rule.who if who is None else who,
        rule.importance if importance is None else importance,
    )
    rule.params = clean.params
    rule.who = clean.who
    rule.importance = clean.importance
    rule.save(update_fields=["params", "who", "importance", "updated_at"])
    return rule


def member_user_ids(corporation: EveCorporation) -> list[int]:
    """Users whose main is in the corporation."""
    return list(
        EvePlayer.objects.filter(
            primary_character__corporation_id=corporation.corporation_id,
            user__isnull=False,
        ).values_list("user_id", flat=True)
    )


def _rules_key(corporation_id: int, rules: list[Rule]) -> str:
    payload = json.dumps(
        [(r.id, r.kind, r.params, r.who) for r in rules], sort_keys=True
    )
    digest = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()
    return f"corp-requirements-pass:{corporation_id}:{digest[:16]}"


def member_pass_rates(corporation: EveCorporation, rules: list[Rule]) -> dict:
    """{"members": n, "rates": {rule id: percent or None}}.

    Percent is over members we could check (unknown left out), None when
    nobody could be checked. Cached per rule set for a few hours.
    """
    if not rules:
        return {"members": 0, "rates": {}}
    key = _rules_key(corporation.corporation_id, rules)
    cached = cache.get(key)
    if cached is not None:
        return cached
    user_ids = member_user_ids(corporation)
    results = evaluate(rules, user_ids)
    rates = {}
    for index, rule in enumerate(rules):
        checked = met = 0
        for checks in results.values():
            status = checks[index].status
            if status == "unknown":
                continue
            checked += 1
            met += status == "met"
        rates[rule.id] = round(100 * met / checked) if checked else None
    value = {"members": len(user_ids), "rates": rates}
    cache.set(key, value, PASS_RATE_TTL)
    return value


def checks_for(corporation: EveCorporation, user_id: int) -> list:
    return evaluate_user(corporation_rules(corporation), user_id)


def apply_blockers(corporation: EveCorporation, user_id: int) -> list:
    """Required rules the user doesn't meet yet; empty means they may apply."""
    rules = [
        rule
        for rule in corporation_rules(corporation)
        if rule.importance == Rule.IMPORTANCE_REQUIRED
    ]
    if not rules:
        return []
    return blocking_checks(evaluate_user(rules, user_id))


def blocked_detail(blockers: list) -> str:
    listed = "; ".join(check.text for check in blockers)
    return f"You don't meet this corporation's requirements yet: {listed}."


def stale_skill_characters(user_id: int) -> list[int]:
    """Pks of the user's characters whose skills haven't synced recently."""
    cutoff = timezone.now() - SKILLS_STALE_AFTER
    fresh = EveCharacterSyncState.objects.filter(
        section=SKILLS, synced_at__gte=cutoff
    ).values("character_id")
    return list(
        EveCharacter.objects.filter(owned_by_q(user_id))
        .filter(esi_deleted=False, esi_suspended=False)
        .exclude(pk__in=fresh)
        .values_list("pk", flat=True)
        .distinct()
    )


def refresh_stale_skills(user_id: int) -> bool:
    """Queue a skills sync for the user's characters with stale skills.

    At most once per user per SKILLS_REFRESH_COOLDOWN. True when a sync was
    queued by this call; the checks pick up the new skills once the
    capability engine re-rates the character (a minute or two).
    """
    key = f"{SKILLS_REFRESH_KEY}:{user_id}"
    if cache.get(key) is not None:
        return False
    pks = stale_skill_characters(user_id)
    if not pks:
        return False
    cache.set(key, 1, SKILLS_REFRESH_COOLDOWN)

    # pylint: disable=import-outside-toplevel
    from eveonline.tasks.character_sync import refresh_character_skills_now

    def _queue():
        for pk in pks:
            try:
                refresh_character_skills_now.delay(pk)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Could not queue skills refresh for %s", pk)

    transaction.on_commit(_queue)
    return True
