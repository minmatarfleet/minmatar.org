import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationApplicationsBlock from "@components/blocks/CorporationApplicationsBlock.astro";

import CorporationBadge from "@components/blocks/CorporationBadge.astro";
vi.mock("@components/blocks/CorporationBadge.astro");

test("CorporationApplicationsBlock defaults", async () => {
  vi.mocked(CorporationBadge).mockResolvedValue("CorporationBadge_component");

  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationApplicationsBlock, {
    props: {
      corporation: {
        corporation_id: 12,
        applications: [],
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
