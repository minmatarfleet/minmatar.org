import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationApplication from "@components/blocks/CorporationApplication.astro";

import CorporationBadge from "@components/blocks/CorporationBadge.astro";
import PilotBadge from "@components/blocks/PilotBadge.astro";
vi.mock("@components/blocks/CorporationBadge.astro");
vi.mock("@components/blocks/PilotBadge.astro");

test("CorporationApplication defaults", async () => {
  vi.mocked(CorporationBadge).mockResolvedValue("CorporationBadge_component");
  vi.mocked(PilotBadge).mockResolvedValue("PilotBadge_component");

  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationApplication, {
    props: {
      application: {
        id: 12,
        character_id: 9909,
        character_name: "Bob",
        corporation_id: 76,
        corporation_name: "bagok",
        status: "pending",
        alts: [],
        description: "I want to blow up noobs",
      },
      corporation_id: 76,
      corporation_name: "rawr",
    },
  });

  expect(result).toMatchSnapshot();
});
