import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductInsightsPanel from "@components/blocks/ProductInsightsPanel.astro";
import { insights } from "./product_fixtures";

const render = async (props: Record<string, unknown>) => {
    const container = await AstroContainer.create();
    return container.renderToString(ProductInsightsPanel, { props });
};

test("a fight that took most losses leads the verdict, and stock is measured against it", async () => {
    const result = await render({ insights: insights(), build_path: "/industry/products/174/build/" });

    expect(result).toContain("Losses are outpacing builds");
    expect(result).toContain("35 lost, 30 of them in one Amamake fight");
    expect(result).toContain("8 hulls short of reshipping a fight that size");
    expect(result).toContain("2 ordered units have no builder.");
    expect(result).toContain('href="/industry/products/174/build/"');
    expect(result).toContain("+ 10 more in small fights across 7 systems.");
    expect(result).toContain("https://zkillboard.com/kill/139068329/");
});

test("without a Build tab the unclaimed note has no link", async () => {
    const result = await render({ insights: insights(), build_path: null });

    expect(result).toContain("2 ordered units have no builder.");
    expect(result).not.toContain("Claim them");
});

test("production that covers sales and losses reads as keeping up", async () => {
    const result = await render({
        insights: insights({
            built: { units_30d: 12, units_90d: 30, jobs_90d: 8, builders_90d: 2, running_units: 0, running_jobs: 0, last_built_at: null },
            losses: { units_30d: 4, units_90d: 6, recent: [], fights: [], small_fight_units: 6, small_fight_systems: 3 },
            running: [],
        }),
    });

    expect(result).toContain("Production is keeping up");
    expect(result).toContain("4 lost and 2 sold against 12 built.");
    expect(result).toContain("Nothing in production right now.");
});

test("items that are not ships show where they sell instead of hangars", async () => {
    const result = await render({
        insights: insights({ is_ship: false, hangars: null, losses: null }),
    });

    expect(result).toContain("Where it sells");
    expect(result).toContain("2 sold against 6 built.");
    expect(result).not.toContain("Where they are");
    expect(result).not.toContain("reship");
});

test("a month with no activity is called quiet", async () => {
    const result = await render({
        insights: insights({
            built: { units_30d: 0, units_90d: 0, jobs_90d: 0, builders_90d: 0, running_units: 0, running_jobs: 0, last_built_at: null },
            sales: { market_units_30d: 0, market_units_90d: 0, contract_units_30d: 0, contract_units_90d: 0, listed_units: 0, lowest_listed_price: null, outstanding_contracts: 0, locations: [] },
            losses: { units_30d: 0, units_90d: 0, recent: [], fights: [], small_fight_units: 0, small_fight_systems: 0 },
            builders: [],
            running: [],
        }),
    });

    expect(result).toContain("Quiet this month");
    expect(result).toContain("Nothing built, sold or lost in the last 30 days.");
    expect(result).toContain("Nobody has finished a job for this in the window.");
});
