import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductBuildInvention from "@components/blocks/ProductBuildInvention.astro";
import ProductBuildCost from "@components/blocks/ProductBuildCost.astro";
import type { ProductBuildInvention as Invention } from "@dtypes/api.minmatar.org";
import { build } from "./product_fixtures";

const invention = (overrides: Partial<Invention> = {}): Invention => ({
    kind: "T2",
    sources: [
        {
            type_id: 954,
            name: "Rupture Blueprint",
            kind: "t1_blueprint",
            base_chance: 0.26,
            runs: 1,
            datacores: [
                { type_id: 20424, name: "Datacore - Mechanical Engineering", quantity: 8, unit_price: 27_546, line_cost: 220_368, strategy: null, industry_product_id: null },
                { type_id: 20416, name: "Datacore - Plasma Physics", quantity: 8, unit_price: 99_198, line_cost: 793_584, strategy: null, industry_product_id: null },
            ],
        },
    ],
    decryptor_name: "Accelerant Decryptor",
    source_name: "Rupture Blueprint",
    chance: 0.447,
    runs_per_copy: 2,
    copy_me: 4,
    copy_te: 14,
    cost_per_unit: 1_590_000,
    ...overrides,
});

const render = async (overrides: Partial<Invention> = {}) => {
    const container = await AstroContainer.create();
    return container.renderToString(ProductBuildInvention, {
        props: { invention: invention(overrides) },
    });
};

test("lists the source, its chance and datacores, and the cheapest way", async () => {
    const result = await render();

    expect(result).toContain("Invented from");
    expect(result).toContain("Rupture Blueprint");
    expect(result).toContain("26% base · 1-run copies");
    expect(result).toContain("8 × Datacore - Plasma Physics");
    expect(result).toContain("1.59M");
    expect(result).toContain("Accelerant Decryptor, 45%");
    expect(result).toContain("2-run ME 4 copies");
});

test("relic products explain relic grades", async () => {
    const result = await render({ kind: "T3", cost_per_unit: null, chance: null, decryptor_name: null });

    expect(result).toContain("ancient relic");
    expect(result).not.toContain("Invention per unit");
    expect(result).not.toContain("Cheapest at Amamake");
});

test("the Build tab margin says it includes invention", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductBuildCost, {
        props: {
            build: build({ invention: invention(), invention_cost: 1_590_000, margin: 15_410_000 }),
            planner_path: "/industry/orders/planner?type_id=12015",
        },
    });

    expect(result).toContain("The margin takes off 1.59M of expected invention");
});
