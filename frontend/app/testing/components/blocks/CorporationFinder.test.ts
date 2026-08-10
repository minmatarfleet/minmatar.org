import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationFinder from "@components/blocks/CorporationFinder.astro";

import { get_alliance_corporations_with_extraction } from "@helpers/fetching/corporations";
vi.mock("@helpers/fetching/corporations");

test("CorporationFinder defaults", async () => {
  vi.mocked(get_alliance_corporations_with_extraction).mockResolvedValue([
    {
      corporation_id: 98794203,
      corporation_name: "Banshee Squadron",
      alliance_id: 99011978,
      alliance_name: "Minmatar Fleet Alliance",
      faction_id: 500002,
      faction_name: "Minmatar Republic",
      type: "alliance",
      introduction: "",
      biography: "",
      executor_notes: "",
      timezones: [],
      requirements: [],
      members: [],
      active: true,
      trial: false,
    },
    {
      corporation_id: 98726134,
      corporation_name: "Rattini Tribe",
      alliance_id: 99011978,
      alliance_name: "Minmatar Fleet Alliance",
      faction_id: 500002,
      faction_name: "Minmatar Republic",
      type: "alliance",
      introduction: "",
      biography: "",
      executor_notes: "",
      timezones: [],
      requirements: [],
      members: [],
      active: true,
      trial: false,
    },
    {
      corporation_id: 98838663,
      corporation_name: "Minmatar Extraction Company",
      alliance_id: 99012009,
      alliance_name: "Minmatar Fleet Associates",
      type: "associate",
      introduction: "",
      biography: "",
      executor_notes: "",
      timezones: [],
      requirements: [],
      members: [],
      active: true,
      trial: false,
    },
  ]);

  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationFinder, {});

  expect(result).toContain("Banshee Squadron");
  expect(result).toContain("Rattini Tribe");
  expect(result).toContain("Minmatar Extraction Company");
  expect(get_alliance_corporations_with_extraction).toHaveBeenCalled();
});
