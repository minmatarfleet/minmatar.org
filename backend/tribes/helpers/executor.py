"""The alliance executor, who stands in for tribes without a chief.

Kept free of other tribes imports: groups.helpers.feature_access uses it.
"""

from django.conf import settings


def executor_character_id() -> int:
    return int(getattr(settings, "ALLIANCE_EXECUTOR_CHARACTER_ID", 0) or 0)


def executor_user_id() -> int | None:
    """The site user id behind the executor character, or None."""
    # pylint: disable-next=import-outside-toplevel
    from eveonline.models import EveCharacter

    character_id = executor_character_id()
    if not character_id:
        return None
    row = (
        EveCharacter.objects.filter(character_id=character_id)
        .values("user_id", "token__user_id")
        .first()
    )
    if row is None:
        return None
    return row["user_id"] or row["token__user_id"]


def user_is_executor_q(user_pk: int):
    """A Q that holds when ``user_pk`` owns the executor character, to fold
    the check into another query; None when no executor is set."""
    # pylint: disable-next=import-outside-toplevel
    from django.db.models import Exists, Q

    # pylint: disable-next=import-outside-toplevel
    from eveonline.models import EveCharacter

    character_id = executor_character_id()
    if not character_id:
        return None
    return Q(
        Exists(
            EveCharacter.objects.filter(character_id=character_id).filter(
                Q(user_id=user_pk) | Q(token__user_id=user_pk)
            )
        )
    )


def is_interim_executor(user, tribe, executor_id=None) -> bool:
    """True when ``tribe`` has no chief and ``user`` is the executor."""
    if tribe is None or tribe.chief_id:
        return False
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    if executor_id is None:
        executor_id = executor_user_id()
    return executor_id is not None and executor_id == user.pk
