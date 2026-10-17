import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductHeader from "@components/blocks/ProductHeader.astro";
import { product } from "./product_fixtures";

test("a product with a blueprint gets Overview and Build tabs and a planner link", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductHeader, {
        props: { product: product(), view: "build" },
    });

    expect(result).toContain("Abaddon");
    expect(result).toContain('href="/industry/products/174/build/"');
    expect(result).toMatch(/aria-current="page"[^>]*>\s*Build/);
    expect(result).toContain("/industry/orders/planner?type_id=24692");
});

test("a harvested item has no Build tab or planner", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductHeader, {
        props: { product: product({ strategy: "harvested", blueprint_or_reaction_type_id: 0 as unknown as number }), view: "overview" },
    });

    expect(result).not.toContain("/build/");
    expect(result).not.toContain("planner");
    expect(result).toContain("Harvested");
});
