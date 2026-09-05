"""PATCH /fitting-buy-orders/{order_id} — update order metadata / stock."""

from decimal import Decimal, InvalidOperation

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_check import ensure_jita_check
from market.helpers.fitting_buy_guide import multibuy_blocked
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)
from market.helpers.fitting_buy_contract_prices import CONTRACT_MARKUP_MAX
from market.models.fitting_buy_order import (
    FittingBuyContractType,
    FittingBuyOrderStatus,
)

PATH = "/fitting-buy-orders/{order_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Update a fitting buy order",
}


class PatchFittingBuyOrderRequest(Schema):
    notes: str | None = None
    status: str | None = None
    stock_paste: str | None = None
    include_hull: bool | None = None
    contract_markup_pct: str | float | int | None = None
    contract_type: str | None = None


def _parse_markup_pct(raw) -> Decimal | None:
    try:
        value = Decimal(str(raw).strip().rstrip("%"))
    except (InvalidOperation, ValueError):
        return None
    if value.is_nan() or value < 0 or value > CONTRACT_MARKUP_MAX:
        return None
    return value.quantize(Decimal("0.1"))


def _apply_status(order, new_status: str):
    if new_status == "purchased":
        new_status = FittingBuyOrderStatus.COMPLETED
    valid = {c.value for c in FittingBuyOrderStatus}
    if new_status not in valid:
        return 400, ErrorResponse(detail="Invalid status.")
    if (
        new_status == FittingBuyOrderStatus.PENDING_FITTING
        and order.status == FittingBuyOrderStatus.DRAFT
    ):
        blocked, reason = multibuy_blocked(order)
        if blocked:
            detail = {
                "shorts": "Resolve Jita shortfalls (swap or allocate) before copying Multibuy.",
                "too_large": "Purchase list exceeds Multibuy's 100-type limit.",
                "jita_pending": "Wait for the Jita depth check to finish.",
            }.get(reason, "Cannot copy Multibuy yet.")
            return 400, ErrorResponse(detail=detail)
    order.status = new_status
    return None


def _apply_contract_settings(order, payload: PatchFittingBuyOrderRequest):
    fields = []
    if payload.contract_markup_pct is not None:
        markup = _parse_markup_pct(payload.contract_markup_pct)
        if markup is None:
            return None, (
                400,
                ErrorResponse(
                    detail=(
                        "Markup must be a percentage between 0 and "
                        f"{int(CONTRACT_MARKUP_MAX)}."
                    )
                ),
            )
        order.contract_markup_pct = markup
        fields.append("contract_markup_pct")
    if payload.contract_type is not None:
        valid_types = {c.value for c in FittingBuyContractType}
        if payload.contract_type not in valid_types:
            return None, (400, ErrorResponse(detail="Invalid contract type."))
        order.contract_type = payload.contract_type
        fields.append("contract_type")
    return fields, None


def patch_fitting_buy_order(
    request, order_id: int, payload: PatchFittingBuyOrderRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    fields = []
    if payload.notes is not None:
        order.notes = payload.notes
        fields.append("notes")
    if payload.status is not None:
        status_err = _apply_status(order, payload.status)
        if status_err:
            return status_err
        fields.append("status")
    if payload.stock_paste is not None:
        order.stock_paste = payload.stock_paste
        fields.append("stock_paste")
    if payload.include_hull is not None:
        order.include_hull = payload.include_hull
        fields.append("include_hull")
    contract_fields, contract_err = _apply_contract_settings(order, payload)
    if contract_err:
        return contract_err
    fields.extend(contract_fields)

    if fields:
        fields.append("updated_at")
        order.save(update_fields=fields)
        if "stock_paste" in fields or "include_hull" in fields:
            sync_order_items(order)
            ensure_jita_check(order, request.user, quiet=True)

    return serialize_order_detail(order, request.user)
