import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationsSlider from "@components/blocks/CorporationsSlider.astro";

test("CorporationsSlider defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationsSlider, {
    props: {
      corporations: [],
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
