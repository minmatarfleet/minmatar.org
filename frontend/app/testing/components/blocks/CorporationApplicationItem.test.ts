import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationApplicationItem from "@components/blocks/CorporationApplicationItem.astro";

test("CorporationApplicationItem defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationApplicationItem, {
    props: {
      application: {
        character_id: 9909,
        character_name: "Bob",
        corporation_id: 76,
        corporation_name: "bagok",
        status: "pending",
      },
      corporation: {
        id: 76,
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
