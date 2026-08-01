"""POST /appraise – price an EVE paste with our buyback rules."""

from ninja import Router

from buyback.endpoints.schemas import (
    BuybackAppraiseRequest,
    BuybackAppraisalLine,
    BuybackAppraisalResponse,
    BuybackRateRules,
)
from buyback.helpers.appraise import appraise_paste
from buyback.models import EveBuybackSettings

router = Router(tags=["Buyback"])


@router.post(
    "/appraise",
    description=(
        "Appraise an EVE inventory paste using alliance buyback rates "
        "against Jita buy at the price baseline."
    ),
    response=BuybackAppraisalResponse,
)
def post_appraise(request, payload: BuybackAppraiseRequest):
    settings = EveBuybackSettings.load()
    result = appraise_paste(payload.paste, settings=settings)

    return BuybackAppraisalResponse(
        lines=[
            BuybackAppraisalLine(
                type_id=line.type_id,
                name=line.name,
                quantity=line.quantity,
                category=line.category,
                rate=line.rate,
                jita_buy=line.jita_buy,
                unit_price=line.unit_price,
                line_total=line.line_total,
                accepted=line.accepted,
                reject_reason=line.reject_reason,
            )
            for line in result.lines
        ],
        offer_total=result.offer_total,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        rate_rules=BuybackRateRules(
            ore_refine=result.rate_rules.get("ore_refine", 0.85),
            ore_jita_buy=result.rate_rules.get("ore_jita_buy", 1.0),
            p1_jita_buy_cap=result.rate_rules.get("p1_jita_buy_cap", 0.9),
            other_jita_buy=result.rate_rules.get("other_jita_buy", 1.0),
        ),
    )
