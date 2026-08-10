"""POST /appraise – price an EVE paste with our buyback rules."""

from ninja import Router

from buyback.endpoints.schemas import (
    BuybackAppraiseRequest,
    BuybackAppraisalLine,
    BuybackAppraisalResponse,
    BuybackRateRules,
)
from buyback.helpers.appraise import appraise_paste
from buyback.helpers.pricing import public_rate_rules
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
    rates = public_rate_rules(result.rate_rules)

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
                rate_reason=line.rate_reason,
            )
            for line in result.lines
        ],
        offer_total=result.offer_total,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        rate_rules=BuybackRateRules(
            ore_refine=rates["ore_refine"],
            demand_jita_buy=rates["demand_jita_buy"],
            surplus_jita_buy=rates["surplus_jita_buy"],
        ),
    )
