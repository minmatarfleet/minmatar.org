import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductBuildQueue from "@components/blocks/ProductBuildQueue.astro";
import { insights } from "./product_fixtures";

test("orders missing a builder come first with a claim link to the order", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductBuildQueue, { props: { insights: insights() } });

    expect(result).toContain("2 without a builder");
    expect(result).toContain("Claim 2");
    expect(result.indexOf("#K7Q2")).toBeLessThan(result.indexOf("#M3XA"));
    expect(result).toContain('href="/industry/orders/11/"');
    expect(result).toContain("Ballah Inc.");
    expect(result).toContain("3 units");
});

test("an empty queue says so", async () => {
    const base = insights();
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductBuildQueue, {
        props: {
            insights: insights({
                orders: { ...base.orders, open_units: 0, open_assigned_units: 0, recent: [] },
                running: [],
                built: { ...base.built, running_units: 0, running_jobs: 0 },
            }),
        },
    });

    expect(result).toContain("No open orders for this right now.");
    expect(result).toContain("Nothing in production right now.");
    expect(result).not.toContain("without a builder");
});
