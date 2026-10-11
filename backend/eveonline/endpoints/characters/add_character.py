"""GET /add - add character using EVE Online SSO."""

from typing import Optional

from django.contrib.auth.decorators import login_required
from esi.decorators import token_required
from eveonline.endpoints.characters._helpers import (
    discord_account_mismatch_redirect,
    handle_add_character_esi_callback,
    reset_api_session_if_unbound_for_esi_add,
    set_or_remove_session_value,
)
from eveonline.helpers.characters import scope_groups_for_token_add
from eveonline.models import EveCharacter
from eveonline.scopes import TokenType, scopes_for_groups

PATH = "add"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Add character using EVE Online SSO",
}


def add_character(
    request,
    redirect_url: str,
    token_type: Optional[TokenType] = None,
    character_id: str = None,
    account_user_id: Optional[int] = None,
):
    reset_api_session_if_unbound_for_esi_add(request)
    request.session["redirect_url"] = redirect_url
    set_or_remove_session_value(request, "add_character_id", character_id)
    mismatch = discord_account_mismatch_redirect(
        request, redirect_url, account_user_id
    )
    if mismatch is not None:
        return mismatch

    character = None
    if character_id:
        character = EveCharacter.objects.filter(
            character_id=character_id
        ).first()

    if not token_type:
        if character:
            try:
                token_type = TokenType(character.esi_token_level or "Basic")
            except (ValueError, TypeError):
                token_type = TokenType.BASIC
        else:
            token_type = TokenType.BASIC
    if character_id and token_type == TokenType.PUBLIC:
        token_type = TokenType.BASIC

    scope_groups = scope_groups_for_token_add(character, token_type)
    scopes = scopes_for_groups(scope_groups)

    @login_required()
    @token_required(scopes=scopes, new=True)
    def wrapped(request, token):
        return handle_add_character_esi_callback(request, token, token_type)

    return wrapped(request)  # pylint: disable=no-value-for-parameter
