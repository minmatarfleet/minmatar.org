import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductBuildMaterials from "@components/blocks/ProductBuildMaterials.astro";
import { build } from "./product_fixtures";

test("lists each material per run, linking the ones we track", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductBuildMaterials, { props: { build: build() } });

    expect(result).toContain('href="/industry/products/92/"');
    expect(result).toContain("9,000,000");
    expect(result).toContain("Not tracked");
    expect(result).toContain("2 materials per run, 1 tracked in our supply chain");
    expect(result).toContain("150M");
});

test("a blueprint without materials says so", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductBuildMaterials, {
        props: { build: build({ materials: [], material_cost: null }) },
    });

    expect(result).toContain("No materials listed for this blueprint.");
});
