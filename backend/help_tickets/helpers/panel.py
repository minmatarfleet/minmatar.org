import hashlib
import json

from help_tickets.models import HelpRequestCategory


def _discord_user_id(user) -> int | None:
    discord_user = getattr(user, "discord_user", None)
    if discord_user is None:
        return None
    return discord_user.id


def _mention_discord_ids(category: HelpRequestCategory) -> list[int]:
    ids: list[int] = []
    if category.tribe_group_id:
        tribe_group = category.tribe_group
        if tribe_group.chief_id is not None:
            chief_id = _discord_user_id(tribe_group.chief)
            if chief_id is not None:
                ids.append(chief_id)
    for user in category.assignees.all():
        discord_id = _discord_user_id(user)
        if discord_id is not None:
            ids.append(discord_id)
    return list(dict.fromkeys(ids))


def _section_label(category: HelpRequestCategory) -> str:
    if category.section:
        return category.section
    if category.tribe_group_id:
        return category.tribe_group.tribe.name
    return "General"


def build_help_ticket_panel_config() -> dict:
    categories = []
    queryset = (
        HelpRequestCategory.objects.filter(is_active=True)
        .select_related(
            "tribe_group__tribe", "tribe_group__chief__discord_user"
        )
        .prefetch_related("assignees__discord_user")
        .order_by("sort_order", "title")
    )
    for category in queryset:
        categories.append(
            {
                "id": category.id,
                "code": category.code,
                "title": category.title,
                "description": category.description,
                "section": _section_label(category),
                "mention_discord_ids": _mention_discord_ids(category),
            }
        )

    payload = {
        "embed_title": "Need help?",
        "embed_description": (
            "Choose a team below. "
            "For alliance or general topics, use the panel above.\n\n"
            "**NOTE:** This is an experimental feature, we are migrating away from "
            "our previous ticket bot. Please use this and report any issues in #public."
        ),
        "categories": categories,
    }
    payload["hash"] = compute_panel_content_hash(payload)
    return payload


def compute_panel_content_hash(config: dict) -> str:
    hash_input = {
        "embed_title": config["embed_title"],
        "embed_description": config["embed_description"],
        "categories": config["categories"],
    }
    serialized = json.dumps(hash_input, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
