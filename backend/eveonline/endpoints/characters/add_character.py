"""GET /add - add character using EVE Online SSO."""

from typing import Optional

from django.contrib.auth.decorators import login_required
from esi.decorators import token_required
from eveonline.endpoints.characters._helpers import (
    handle_add_character_esi_callback,
    set_or_remove_session_value,
)
from eveonline.models import EveCharacter
from eveonline.scopes import TokenType, scopes_for

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
):
    request.session["redirect_url"] = redirect_url
    set_or_remove_session_value(request, "add_character_id", character_id)
    if not token_type:
        if (
            character_id
            and EveCharacter.objects.filter(character_id=character_id).exists()
        ):
            char = EveCharacter.objects.get(character_id=character_id)
            try:
                token_type = TokenType(char.esi_token_level or "Basic")
            except (ValueError, TypeError):
                token_type = TokenType.BASIC
        else:
            token_type = TokenType.BASIC
    if character_id and token_type == TokenType.PUBLIC:
        token_type = TokenType.BASIC
    scopes = scopes_for(token_type)

    @login_required()
    @token_required(scopes=scopes, new=True)
    def wrapped(request, token):
        return handle_add_character_esi_callback(request, token, token_type)

    return wrapped(request)  # pylint: disable=no-value-for-parameter
