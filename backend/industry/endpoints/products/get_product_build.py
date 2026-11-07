"""
GET /products/{product_id}/build - one run's materials, prices and margin.

Base blueprint numbers (no ME/TE, facility bonuses, job fees, taxes or
freight) priced like the planner prices materials and the product: Jita
sell at the price_baseline book, else the Forge guide. The planner and
order profit add the rest through plan_costing.

T2/T3 products also get how the copy is invented, and the margin subtracts
the cheapest expected invention cost at Amamake.
"""

import logging

from eveuniverse.models import EveType

from app.errors import ErrorResponse
from industry.endpoints.products.schemas import (
    ProductBuild,
    ProductBuildInvention,
    ProductBuildInventionSource,
    ProductBuildMaterial,
)
from industry.helpers.build_planner import get_recipe
from industry.helpers.cost_breakdown import jita_sell_unit_prices_by_type_id
from industry.helpers.invention_planner import (
    invention_outcomes,
    quote_invention,
    tech_kind,
)
from industry.helpers.type_breakdown import ACTIVITY_REACTION
from industry.models import IndustryProduct

logger = logging.getLogger(__name__)

PATH = "{int:product_id}/build"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Materials for one run of an industry product at Jita sell prices",
    "response": {
        200: ProductBuild,
        404: ErrorResponse,
    },
}


def _invention_block(eve_type, products_per_run):
    """(ProductBuildInvention, invention ISK per run) or (None, None)."""
    outcomes = invention_outcomes(eve_type.id)
    if not outcomes:
        return None, None
    datacore_ids = {int(tid) for o in outcomes for tid, _ in o.materials}
    prices = {
        tid: float(price)
        for tid, price in jita_sell_unit_prices_by_type_id(
            list(datacore_ids)
        ).items()
        if price
    }
    names = dict(
        EveType.objects.filter(id__in=datacore_ids).values_list("id", "name")
    )
    sources = [
        ProductBuildInventionSource(
            type_id=o.source_type_id,
            name=o.source_name,
            kind=o.source_kind,
            base_chance=o.probability,
            runs=o.runs,
            datacores=[
                ProductBuildMaterial(
                    type_id=int(tid),
                    name=names.get(int(tid), str(tid)),
                    quantity=int(qty),
                    unit_price=prices.get(int(tid)),
                    line_cost=(
                        prices[int(tid)] * int(qty)
                        if int(tid) in prices
                        else None
                    ),
                )
                for tid, qty in o.materials
            ],
        )
        for o in outcomes
    ]
    block = ProductBuildInvention(kind=tech_kind(outcomes), sources=sources)
    try:
        best = quote_invention(eve_type, products_per_run, "amamake").best
    except ValueError:
        logger.info("No invention quote for %s", eve_type.id, exc_info=True)
        return block, None
    block.decryptor_name = best.decryptor.name
    block.source_name = best.source.source_name
    block.chance = best.chance
    block.runs_per_copy = best.runs_per_copy
    block.copy_me = best.copy_me
    block.copy_te = best.copy_te
    block.cost_per_unit = best.invention_per_unit_isk
    return block, best.invention_isk


def get_product_build(request, product_id: int):
    product = (
        IndustryProduct.objects.select_related("eve_type")
        .filter(pk=product_id)
        .first()
    )
    if product is None:
        return 404, ErrorResponse(
            detail=f"Industry product {product_id} not found."
        )
    recipe = get_recipe(product.eve_type_id)
    if recipe is None:
        return 404, ErrorResponse(
            detail=f"{product.eve_type.name} has no blueprint or reaction."
        )

    material_ids = [type_id for type_id, _, _ in recipe.materials]
    prices = {
        type_id: float(price)
        for type_id, price in jita_sell_unit_prices_by_type_id(
            [*material_ids, recipe.product_type_id]
        ).items()
        if price
    }
    tracked = {
        type_id: (pk, strategy)
        for pk, type_id, strategy in IndustryProduct.objects.filter(
            eve_type_id__in=material_ids
        ).values_list("pk", "eve_type_id", "strategy")
    }

    materials = []
    for type_id, name, quantity in sorted(
        recipe.materials,
        key=lambda m: prices.get(m[0], 0) * m[2],
        reverse=True,
    ):
        unit_price = prices.get(type_id)
        industry_product_id, strategy = tracked.get(type_id, (None, None))
        materials.append(
            ProductBuildMaterial(
                type_id=type_id,
                name=name,
                quantity=quantity,
                unit_price=unit_price,
                line_cost=unit_price * quantity if unit_price else None,
                strategy=strategy,
                industry_product_id=industry_product_id,
            )
        )

    priced = [m.line_cost for m in materials if m.line_cost is not None]
    material_cost = sum(priced) if materials else None
    sell_price = prices.get(recipe.product_type_id)
    run_value = (
        sell_price * recipe.product_quantity
        if sell_price is not None
        else None
    )
    complete = len(priced) == len(materials)
    invention, invention_cost = _invention_block(
        product.eve_type, recipe.product_quantity
    )
    margin = (
        run_value - material_cost
        if complete and run_value is not None and material_cost is not None
        else None
    )
    if margin is not None and invention is not None:
        margin = (
            margin - invention_cost if invention_cost is not None else None
        )
    return 200, ProductBuild(
        product_id=product.pk,
        type_id=recipe.product_type_id,
        blueprint_type_id=recipe.blueprint_type_id,
        activity=(
            "reaction"
            if recipe.activity_id == ACTIVITY_REACTION
            else "manufacturing"
        ),
        products_per_run=recipe.product_quantity,
        time_seconds=recipe.base_time,
        sell_price=sell_price,
        material_cost=material_cost,
        margin=margin,
        prices_complete=complete,
        materials=materials,
        invention=invention,
        invention_cost=invention_cost,
    )
