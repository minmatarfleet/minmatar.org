import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationSlide from "@components/blocks/CorporationSlide.astro";

test("CorporationSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationSlide, {
    props: {
      id: 65,
      ceo_image: "chicken.gif",
      ceo_character_id: 89,
      corporation: {
        corporation_id: 65,
        corporation_name: "chicken attack",
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
