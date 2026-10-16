import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CampaignSitesTable from "@components/blocks/CampaignSitesTable.astro";
import type { CampaignSite } from "@dtypes/api.minmatar.org";

const site = (overrides: Partial<CampaignSite>): CampaignSite => ({
    id: 1,
    occurred_at: "2026-10-16T00:12:00Z",
    site_kind: "complex",
    amount_lp: 52500,
    system: "Helgatild",
    username: "thumper",
    character_id: 1,
    character_name: "thumper is sad",
    plex_class: "",
    plex_size: "",
    confidence: "",
    ...overrides,
});

test("a complex shows its size, or the payout when the size is unknown", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(CampaignSitesTable, {
        props: {
            sites: [
                site({ id: 1, plex_size: "Medium", amount_lp: 22500 }),
                site({ id: 2, plex_size: "", amount_lp: 52500, character_name: "Orion Blackthorn" }),
                site({ id: 3, site_kind: "advantage_site", amount_lp: 10000, character_name: "Ais Rollard" }),
            ],
        },
    });

    expect(result).toContain("Medium complex");
    expect(result).toContain("52,500 LP");
    expect(result).toContain("Advantage site");
    expect(result).not.toContain(">Complex<");
});
