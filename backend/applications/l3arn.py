import re

L3ARN_CORPORATION_NAME = "Minmatar Fleet Academy"

HOW_FOUND_LINE_PATTERN = re.compile(r"\n- How I found you:.*")

DISCORD_MESSAGE_MAX_LENGTH = 2000
L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD = 300
L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH = (
    DISCORD_MESSAGE_MAX_LENGTH - L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD
)

L3ARN_APPLICATION_FIELD_LIMITS = {
    "introduction": 300,
    "goals": 180,
    "how_found_other": 80,
    "main_character_name": 37,
    "other_alliance_affiliation": 40,
}


def is_l3arn_corporation(corporation) -> bool:
    return (
        corporation is not None and corporation.name == L3ARN_CORPORATION_NAME
    )


def l3arn_discord_description(description: str) -> str:
    """Strip web-only questionnaire lines before Discord posting or length checks."""
    return HOW_FOUND_LINE_PATTERN.sub("", description)


def validate_l3arn_application_description(description: str) -> str | None:
    """Return an error message when the description exceeds Discord-safe limits."""
    if (
        len(l3arn_discord_description(description))
        > L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH
    ):
        return (
            "Application text exceeds the maximum length allowed for Discord."
        )

    return None
