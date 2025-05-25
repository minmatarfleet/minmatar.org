import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationPicture from "@components/blocks/CorporationPicture.astro";

test("CorporationPicture defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationPicture, {
    props: {
      corporations_id: 65,
      corporation_name: "death chick",
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
