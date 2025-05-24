import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ComponentBlock from "@components/blocks/ComponentBlock.astro";

test("ComponentBlock defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ComponentBlock, {
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
