"""Loyalty / LP buyback router."""

from ninja import Router

from industry.endpoints.loyalty.delete_order_claim import (
    PATH as delete_order_claim_path,
    ROUTE_SPEC as delete_order_claim_spec,
    delete_order_claim,
    METHOD as delete_order_claim_method,
)
from industry.endpoints.loyalty.get_capabilities import (
    PATH as get_capabilities_path,
    ROUTE_SPEC as get_capabilities_spec,
    get_capabilities,
    METHOD as get_capabilities_method,
)
from industry.endpoints.loyalty.get_currencies import (
    PATH as get_currencies_path,
    ROUTE_SPEC as get_currencies_spec,
    get_currencies,
    METHOD as get_currencies_method,
)
from industry.endpoints.loyalty.get_ledger import (
    PATH as get_ledger_path,
    ROUTE_SPEC as get_ledger_spec,
    get_ledger,
    METHOD as get_ledger_method,
)
from industry.endpoints.loyalty.get_offers import (
    PATH as get_offers_path,
    ROUTE_SPEC as get_offers_spec,
    get_offers,
    METHOD as get_offers_method,
)
from industry.endpoints.loyalty.get_order import (
    PATH as get_order_path,
    ROUTE_SPEC as get_order_spec,
    get_order,
    METHOD as get_order_method,
)
from industry.endpoints.loyalty.get_orders import (
    PATH as get_orders_path,
    ROUTE_SPEC as get_orders_spec,
    get_orders,
    METHOD as get_orders_method,
)
from industry.endpoints.loyalty.get_stats import (
    PATH as get_stats_path,
    ROUTE_SPEC as get_stats_spec,
    get_stats,
    METHOD as get_stats_method,
)
from industry.endpoints.loyalty.patch_order import (
    PATH as patch_order_path,
    ROUTE_SPEC as patch_order_spec,
    patch_order,
    METHOD as patch_order_method,
)
from industry.endpoints.loyalty.post_order_claim import (
    PATH as post_order_claim_path,
    ROUTE_SPEC as post_order_claim_spec,
    post_order_claim,
    METHOD as post_order_claim_method,
)
from industry.endpoints.loyalty.post_order_discord_ack import (
    PATH as post_order_discord_ack_path,
    ROUTE_SPEC as post_order_discord_ack_spec,
    post_order_discord_ack,
    METHOD as post_order_discord_ack_method,
)
from industry.endpoints.loyalty.post_orders import (
    PATH as post_orders_path,
    ROUTE_SPEC as post_orders_spec,
    post_orders,
    METHOD as post_orders_method,
)
from industry.endpoints.loyalty.get_settings import (
    PATH as get_settings_path,
    ROUTE_SPEC as get_settings_spec,
    get_settings,
    METHOD as get_settings_method,
)
from industry.endpoints.loyalty.get_settings_history import (
    PATH as get_settings_history_path,
    ROUTE_SPEC as get_settings_history_spec,
    get_settings_history,
    METHOD as get_settings_history_method,
)
from industry.endpoints.loyalty.post_settings_currency import (
    PATH as post_settings_currency_path,
    ROUTE_SPEC as post_settings_currency_spec,
    post_settings_currency,
    METHOD as post_settings_currency_method,
)
from industry.endpoints.loyalty.patch_settings_currency import (
    PATH as patch_settings_currency_path,
    ROUTE_SPEC as patch_settings_currency_spec,
    patch_settings_currency,
    METHOD as patch_settings_currency_method,
)
from industry.endpoints.loyalty.post_settings_account import (
    PATH as post_settings_account_path,
    ROUTE_SPEC as post_settings_account_spec,
    post_settings_account,
    METHOD as post_settings_account_method,
)
from industry.endpoints.loyalty.patch_settings_account import (
    PATH as patch_settings_account_path,
    ROUTE_SPEC as patch_settings_account_spec,
    patch_settings_account,
    METHOD as patch_settings_account_method,
)
from industry.endpoints.loyalty.post_settings_contact import (
    PATH as post_settings_contact_path,
    ROUTE_SPEC as post_settings_contact_spec,
    post_settings_contact,
    METHOD as post_settings_contact_method,
)
from industry.endpoints.loyalty.patch_settings_contact import (
    PATH as patch_settings_contact_path,
    ROUTE_SPEC as patch_settings_contact_spec,
    patch_settings_contact,
    METHOD as patch_settings_contact_method,
)
from industry.endpoints.loyalty.delete_settings_contact import (
    PATH as delete_settings_contact_path,
    ROUTE_SPEC as delete_settings_contact_spec,
    delete_settings_contact,
    METHOD as delete_settings_contact_method,
)

router = Router(tags=["Industry - Loyalty"])

_ROUTES = (
    (
        get_currencies_method,
        get_currencies_path,
        get_currencies_spec,
        get_currencies,
    ),
    (get_ledger_method, get_ledger_path, get_ledger_spec, get_ledger),
    (get_offers_method, get_offers_path, get_offers_spec, get_offers),
    (
        get_capabilities_method,
        get_capabilities_path,
        get_capabilities_spec,
        get_capabilities,
    ),
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (get_order_method, get_order_path, get_order_spec, get_order),
    (get_stats_method, get_stats_path, get_stats_spec, get_stats),
    (post_orders_method, post_orders_path, post_orders_spec, post_orders),
    (
        post_order_claim_method,
        post_order_claim_path,
        post_order_claim_spec,
        post_order_claim,
    ),
    (
        delete_order_claim_method,
        delete_order_claim_path,
        delete_order_claim_spec,
        delete_order_claim,
    ),
    (
        post_order_discord_ack_method,
        post_order_discord_ack_path,
        post_order_discord_ack_spec,
        post_order_discord_ack,
    ),
    (patch_order_method, patch_order_path, patch_order_spec, patch_order),
    (get_settings_method, get_settings_path, get_settings_spec, get_settings),
    (
        get_settings_history_method,
        get_settings_history_path,
        get_settings_history_spec,
        get_settings_history,
    ),
    (
        post_settings_currency_method,
        post_settings_currency_path,
        post_settings_currency_spec,
        post_settings_currency,
    ),
    (
        patch_settings_currency_method,
        patch_settings_currency_path,
        patch_settings_currency_spec,
        patch_settings_currency,
    ),
    (
        post_settings_account_method,
        post_settings_account_path,
        post_settings_account_spec,
        post_settings_account,
    ),
    (
        patch_settings_account_method,
        patch_settings_account_path,
        patch_settings_account_spec,
        patch_settings_account,
    ),
    (
        post_settings_contact_method,
        post_settings_contact_path,
        post_settings_contact_spec,
        post_settings_contact,
    ),
    (
        patch_settings_contact_method,
        patch_settings_contact_path,
        patch_settings_contact_spec,
        patch_settings_contact,
    ),
    (
        delete_settings_contact_method,
        delete_settings_contact_path,
        delete_settings_contact_spec,
        delete_settings_contact,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
