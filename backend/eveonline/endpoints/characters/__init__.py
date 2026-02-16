"""One router for the entire characters area. Every endpoint registered directly."""

from ninja import Router

from eveonline.endpoints.characters.add_character import (
    PATH as add_character_path,
    ROUTE_SPEC as add_character_spec,
    add_character,
    METHOD as add_character_method,
)
from eveonline.endpoints.characters.delete_character_by_id import (
    PATH as delete_character_by_id_path,
    ROUTE_SPEC as delete_character_by_id_spec,
    delete_character_by_id,
    METHOD as delete_character_by_id_method,
)
from eveonline.endpoints.characters.tags.delete_character_tag import (
    PATH as delete_character_tag_path,
    ROUTE_SPEC as delete_character_tag_spec,
    delete_character_tag,
    METHOD as delete_character_tag_method,
)
from eveonline.endpoints.characters.get_assets_for_character import (
    PATH as get_assets_path,
    ROUTE_SPEC as get_assets_spec,
    get_assets_for_character_by_id,
    METHOD as get_assets_method,
)
from eveonline.endpoints.characters.get_character_by_id import (
    PATH as get_character_by_id_path,
    ROUTE_SPEC as get_character_by_id_spec,
    get_character_by_id,
    METHOD as get_character_by_id_method,
)
from eveonline.endpoints.characters.get_character_tokens import (
    PATH as get_character_tokens_path,
    ROUTE_SPEC as get_character_tokens_spec,
    get_character_tokens,
    METHOD as get_character_tokens_method,
)
from eveonline.endpoints.characters.tags.get_character_tags import (
    PATH as get_character_tags_path,
    ROUTE_SPEC as get_character_tags_spec,
    get_character_tags,
    METHOD as get_character_tags_method,
)
from eveonline.endpoints.characters.get_characters import (
    PATH as get_characters_path,
    ROUTE_SPEC as get_characters_spec,
    get_characters,
    METHOD as get_characters_method,
)
from eveonline.endpoints.characters.get_primary import (
    PATH as get_primary_path,
    ROUTE_SPEC as get_primary_spec,
    get_primary_character,
    METHOD as get_primary_method,
)
from eveonline.endpoints.characters.get_skillsets_for_character import (
    PATH as get_skillsets_path,
    ROUTE_SPEC as get_skillsets_spec,
    get_skillsets_for_character_by_id,
    METHOD as get_skillsets_method,
)
from eveonline.endpoints.characters.get_summary import (
    PATH as get_summary_path,
    ROUTE_SPEC as get_summary_spec,
    get_summary,
    METHOD as get_summary_method,
)
from eveonline.endpoints.characters.tags.get_tags import (
    PATH as get_tags_path,
    ROUTE_SPEC as get_tags_spec,
    get_tags,
    METHOD as get_tags_method,
)
from eveonline.endpoints.characters.tags.post_character_tags import (
    PATH as post_character_tags_path,
    ROUTE_SPEC as post_character_tags_spec,
    post_character_tags,
    METHOD as post_character_tags_method,
)
from eveonline.endpoints.characters.put_primary import (
    PATH as put_primary_path,
    ROUTE_SPEC as put_primary_spec,
    put_primary_character,
    METHOD as put_primary_method,
)
from eveonline.endpoints.characters.tags.put_character_tags import (
    PATH as put_character_tags_path,
    ROUTE_SPEC as put_character_tags_spec,
    put_character_tags,
    METHOD as put_character_tags_method,
)

router = Router(tags=["Characters"])

_ROUTES = (
    (
        get_characters_method,
        get_characters_path,
        get_characters_spec,
        get_characters,
    ),
    (get_tags_method, get_tags_path, get_tags_spec, get_tags),
    (
        get_character_by_id_method,
        get_character_by_id_path,
        get_character_by_id_spec,
        get_character_by_id,
    ),
    (
        get_skillsets_method,
        get_skillsets_path,
        get_skillsets_spec,
        get_skillsets_for_character_by_id,
    ),
    (
        get_assets_method,
        get_assets_path,
        get_assets_spec,
        get_assets_for_character_by_id,
    ),
    (
        delete_character_by_id_method,
        delete_character_by_id_path,
        delete_character_by_id_spec,
        delete_character_by_id,
    ),
    (
        get_primary_method,
        get_primary_path,
        get_primary_spec,
        get_primary_character,
    ),
    (
        put_primary_method,
        put_primary_path,
        put_primary_spec,
        put_primary_character,
    ),
    (
        add_character_method,
        add_character_path,
        add_character_spec,
        add_character,
    ),
    (get_summary_method, get_summary_path, get_summary_spec, get_summary),
    (
        get_character_tokens_method,
        get_character_tokens_path,
        get_character_tokens_spec,
        get_character_tokens,
    ),
    (
        get_character_tags_method,
        get_character_tags_path,
        get_character_tags_spec,
        get_character_tags,
    ),
    (
        post_character_tags_method,
        post_character_tags_path,
        post_character_tags_spec,
        post_character_tags,
    ),
    (
        put_character_tags_method,
        put_character_tags_path,
        put_character_tags_spec,
        put_character_tags,
    ),
    (
        delete_character_tag_method,
        delete_character_tag_path,
        delete_character_tag_spec,
        delete_character_tag,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
