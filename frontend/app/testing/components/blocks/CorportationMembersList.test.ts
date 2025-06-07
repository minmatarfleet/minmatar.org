import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationMembersList from "@components/blocks/CorporationMembersList.astro";

test("CorporationMembersList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationMembersList, {
    props: {
      corporations: [],
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
