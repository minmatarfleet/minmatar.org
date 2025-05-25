import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationBadge from "@components/blocks/CorporationBadge.astro";

import { get_corporation_by_id } from "@helpers/api.eveonline/corporations";
vi.mock("@helpers/api.eveonline/corporations");

test("CorporationBadge defaults", async () => {
  vi.mocked(get_corporation_by_id).mockResolvedValue({
    alliance_id: 43,
    ceo_id: 98,
    creator_id: 98,
    date_founded: new Date("2100-01-01"),
    description: "a great corp",
    faction_id: 1,
    home_station_id: 65,
    member_count: 91,
    name: "chicken attack",
    shares: 12,
    tax_rate: 1,
    ticker: "CHICK",
    url: "chicken.com",
    war_eligible: true,
  });
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationBadge, {
    props: {
      corporation: {
        id: 12,
        name: "chicken attack",
      },
    },
  });

  expect(result).toMatchSnapshot();
});
