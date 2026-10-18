"""
GET /products/{product_id}/build - one run's materials, prices and margin.

Base blueprint numbers (no ME/TE, facility bonuses, job fees, taxes or
freight) priced like the planner prices materials and the product: Jita
sell at the price_baseline book, else the Forge guide. The planner and
order profit add the rest through plan_costing.
"""

from app.errors import ErrorResponse
from industry.endpoints.products.schemas import (
    ProductBuild,
    ProductBuildMaterial,
)
from industry.helpers.build_planner import get_recipe
from industry.helpers.cost_breakdown import jita_sell_unit_prices_by_type_id
from industry.helpers.type_breakdown import ACTIVITY_REACTION
from industry.models import IndustryProduct

PATH = "{int:product_id}/build"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Materials for one run of an industry product at Jita sell prices",
    "response": {
        200: ProductBuild,
        404: ErrorResponse,
    },
}


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
        margin=(
            run_value - material_cost
            if complete and run_value is not None and material_cost is not None
            else None
        ),
        prices_complete=complete,
        materials=materials,
    )
