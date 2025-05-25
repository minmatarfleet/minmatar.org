import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationHistory from "@components/blocks/CorporationHistory.astro";

import { get_corporation_history } from "@helpers/api.eveonline/characters";
import CorporationBadge from "@components/blocks/CorporationBadge.astro";
import { get_names_and_categories_by_ids } from "@helpers/api.eveonline/universe";
vi.mock("@helpers/api.eveonline/characters");
vi.mock("@components/blocks/CorporationBadge.astro");
vi.mock("@helpers/api.eveonline/universe");

test("CorporationHistory defaults", async () => {
  vi.mocked(get_corporation_history).mockResolvedValue([
    {
      corporation_id: 12,
      record_id: 65,
      start_date: new Date("2100-01-01"),
    },
  ]);
  vi.mocked(get_names_and_categories_by_ids).mockResolvedValue([
    {
      category: "place",
      id: 3,
      name: "stuff",
    },
  ]);

  vi.mocked(CorporationBadge).mockReturnValue("CorporationBadge_component");
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationHistory, {
    props: {
      character_id: 12,
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
