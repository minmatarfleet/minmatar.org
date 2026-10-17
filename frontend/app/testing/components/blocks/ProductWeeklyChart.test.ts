import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ProductWeeklyChart from "@components/blocks/ProductWeeklyChart.astro";
import { days_ago, weeks } from "./product_fixtures";

test("labels the week of a fight with its system and stacks losses with sales", async () => {
    const weekly = weeks([{ built: 2 }, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, { lost: 30, sold: 1 }, {}]);
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductWeeklyChart, {
        props: {
            weekly,
            show_lost: true,
            fights: [{
                solar_system_id: 1, solar_system_name: "Amamake",
                started_at: new Date(new Date(weekly[11].week_start).getTime() + 60_000).toISOString(),
                ended_at: days_ago(7), units: 30, killmail_id: 1,
            }],
        },
    });

    expect(result).toContain("Amamake");
    expect(result).toContain(">31<");
    expect(result).toContain("Lost");
});

test("hides the lost series for items we do not track losses for", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductWeeklyChart, {
        props: { weekly: weeks([{ built: 1, lost: 5, sold: 2 }]), show_lost: false },
    });

    expect(result).not.toContain("swatch-lost");
    expect(result).toContain(">2<");
});

test("says so when nothing moved", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(ProductWeeklyChart, {
        props: { weekly: weeks(), show_lost: true },
    });

    expect(result).toContain("Nothing built, sold or lost in the last 13 weeks.");
});
