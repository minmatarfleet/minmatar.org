import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationItem from "@components/blocks/CorporationItem.astro";

test("CorporationItem defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationItem, {
    props: {
      corporation: {
        corporation_id: 2345,
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
