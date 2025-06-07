import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationApplicationsList from "@components/blocks/CorporationApplicationsList.astro";

import CorporationApplicationsBlock from "@components/blocks/CorporationApplicationsBlock.astro";
vi.mock("@components/blocks/CorporationApplicationsBlock.astro");

test("CorporationApplicationsList defaults", async () => {
  vi.mocked(CorporationApplicationsBlock).mockResolvedValue(
    "CorporationApplicationsBlock_component"
  );
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationApplicationsList, {
    props: {
      corporations: [
        {
          corporation_id: 12,
          applications: [],
        },
        {
          corporation_id: 11432,
          applications: [],
        },
      ],
    },
  });

  // expect(result).toMatchSnapshot();
});
