"""Class requirements and the check against one pilot.

A class stores rows like {"kind": "accounts", "value": "2"}. Every kind is
something the site already knows about the pilot, so the check needs nothing
new: alliance tenure, classes done, linked accounts, a doctrine fit ready
(capability engine), a certificate, a tribe group, a corporation.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from capabilities.models import CharacterAccount, CharacterFittingReadiness
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter, EveCorporation
from groups.models import UserCommunityStatusHistory
from learning.models import MentorClass, MentorRequest, UserCertificateAward
from tribes.models import TribeGroup, TribeGroupMembership

KIND_ALLIANCE_DAYS = "alliance_days"
KIND_CLASS_DONE = "class_done"
KIND_ACCOUNTS = "accounts"
KIND_READY_FIT = "ready_fit"
KIND_CERTIFICATE = "certificate"
KIND_TRIBE_GROUP = "tribe_group"
KIND_CORPORATION = "corporation"

KIND_LABELS = {
    KIND_ALLIANCE_DAYS: "In the alliance at least (days)",
    KIND_CLASS_DONE: "Class done (one of these class slugs)",
    KIND_ACCOUNTS: "Accounts linked (at least)",
    KIND_READY_FIT: "A doctrine fit ready on any character",
    KIND_CERTIFICATE: "Certificate earned (slug)",
    KIND_TRIBE_GROUP: "Member of a tribe group (code)",
    KIND_CORPORATION: "In a corporation (ticker)",
}
KINDS = tuple(KIND_LABELS)


class RequirementError(ValueError):
    pass


@dataclass
class Check:
    kind: str
    value: str
    label: str
    met: bool
    detail: str


def _number(value: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise RequirementError("Use a whole number.") from exc
    if number < 0 or number > 10000:
        raise RequirementError("Use a whole number from 0 to 10000.")
    return number


def _list(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(",") if part.strip()]


def clean(rows) -> list[dict]:
    """Validate requirement rows from the editor."""
    cleaned = []
    for row in rows or []:
        kind = str((row or {}).get("kind", "")).strip()
        value = str((row or {}).get("value", "")).strip()
        if kind not in KIND_LABELS:
            raise RequirementError(f"Unknown requirement: {kind or 'empty'}.")
        if kind in (KIND_ALLIANCE_DAYS, KIND_ACCOUNTS):
            value = str(_number(value))
        elif kind == KIND_READY_FIT:
            value = ""
        elif not _list(value):
            raise RequirementError(f"{KIND_LABELS[kind]} needs a value.")
        cleaned.append({"kind": kind, "value": value})
    if len(cleaned) > 10:
        raise RequirementError("A class can have at most 10 requirements.")
    return cleaned


def describe(row: dict) -> str:
    kind, value = row["kind"], row.get("value", "")
    if kind == KIND_ALLIANCE_DAYS:
        return f"In the alliance {value} days"
    if kind == KIND_CLASS_DONE:
        return "Class done: " + " or ".join(_class_titles(_list(value)))
    if kind == KIND_ACCOUNTS:
        return f"{value} accounts linked to your profile"
    if kind == KIND_READY_FIT:
        return "A doctrine fit ready on any character"
    if kind == KIND_CERTIFICATE:
        return "Certificate: " + " or ".join(_list(value))
    if kind == KIND_TRIBE_GROUP:
        return "Member of " + " or ".join(_group_names(_list(value)))
    if kind == KIND_CORPORATION:
        return "In " + " or ".join(_list(value))
    return kind


def _class_titles(slugs: list[str]) -> list[str]:

    titles = dict(
        MentorClass.objects.filter(slug__in=slugs).values_list("slug", "title")
    )
    return [titles.get(slug, slug) for slug in slugs]


def _group_names(codes: list[str]) -> list[str]:

    names = dict(
        TribeGroup.objects.filter(code__in=codes).values_list("code", "name")
    )
    return [names.get(code, code) for code in codes]


def alliance_days(user) -> int:

    first = (
        UserCommunityStatusHistory.objects.filter(user=user)
        .order_by("changed_at")
        .values_list("changed_at", flat=True)
        .first()
    )
    start = first or user.date_joined
    return max(0, (timezone.now() - start).days)


def account_count(user) -> int:
    """EVE accounts linked: inferred accounts plus characters on none."""

    accounts = CharacterAccount.objects.filter(user=user).count()
    loose = (
        EveCharacter.objects.filter(user=user)
        .exclude(account_membership__account__isnull=False)
        .count()
    )
    return accounts + loose


def has_ready_fit(user) -> bool:

    return CharacterFittingReadiness.objects.filter(
        character__user=user, doctrine_ready=True
    ).exists()


def done_class_slugs(user) -> set[str]:

    return set(
        MentorRequest.objects.filter(
            pilot=user, status=MentorRequest.STATUS_DONE
        ).values_list("mentor_class__slug", flat=True)
    )


def check(user, rows) -> list[Check]:
    """Every requirement of a class, met or not, for this pilot."""

    checks = []
    for row in rows or []:
        kind, value = row.get("kind"), str(row.get("value", ""))
        if kind not in KIND_LABELS:
            continue
        met, detail = False, ""
        if kind == KIND_ALLIANCE_DAYS:
            days = alliance_days(user)
            met, detail = days >= _number(value), f"{days} days"
        elif kind == KIND_CLASS_DONE:
            done = done_class_slugs(user) & set(_list(value))
            met = bool(done)
            detail = (
                "Done: " + ", ".join(_class_titles(sorted(done)))
                if done
                else "Not done yet"
            )
        elif kind == KIND_ACCOUNTS:
            count = account_count(user)
            met, detail = count >= _number(value), f"You have {count}"
        elif kind == KIND_READY_FIT:
            met = has_ready_fit(user)
            detail = "You have a ready fit" if met else "No ready fit yet"
        elif kind == KIND_CERTIFICATE:
            met = UserCertificateAward.objects.filter(
                user=user, certificate__slug__in=_list(value)
            ).exists()
            detail = "Earned" if met else "Not earned yet"
        elif kind == KIND_TRIBE_GROUP:
            met = TribeGroupMembership.objects.filter(
                user=user,
                tribe_group__code__in=_list(value),
                status=TribeGroupMembership.STATUS_ACTIVE,
            ).exists()
            detail = "Member" if met else "Not a member"
        elif kind == KIND_CORPORATION:
            main = user_primary_character(user)
            ticker = ""
            if main and main.corporation_id:

                ticker = (
                    EveCorporation.objects.filter(
                        corporation_id=main.corporation_id
                    )
                    .values_list("ticker", flat=True)
                    .first()
                    or ""
                )
            met = ticker in _list(value)
            detail = ticker or "No corporation"
        checks.append(
            Check(
                kind=kind,
                value=value,
                label=describe(row),
                met=met,
                detail=detail,
            )
        )
    return checks
