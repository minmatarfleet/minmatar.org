import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ComponentBlockHeader from "@components/blocks/ComponentBlockHeader.astro";

test("ComponentBlockHeader defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ComponentBlockHeader, {
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
