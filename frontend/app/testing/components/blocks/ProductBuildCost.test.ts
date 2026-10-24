import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductBuildCost from "@components/blocks/ProductBuildCost.astro";
import { build } from "./product_fixtures";

const render = async (overrides = {}) => {
    const container = await AstroContainer.create();
    return container.renderToString(ProductBuildCost, {
        props: { build: build(overrides), planner_path: "/industry/orders/planner?type_id=24692" },
    });
};

test("shows one run's value, cost, margin and time", async () => {
    const result = await render();

    expect(result).toContain("167M");
    expect(result).toContain("150M");
    expect(result).toContain("17M");
    expect(result).toContain("1d 6h");
    expect(result).toContain("/industry/orders/planner?type_id=24692");
});

test("an unknown price leaves the margin blank and says why", async () => {
    const result = await render({ margin: null, prices_complete: false });

    expect(result).toContain("Some materials have no market price yet");
    expect(result).toContain("—");
});
