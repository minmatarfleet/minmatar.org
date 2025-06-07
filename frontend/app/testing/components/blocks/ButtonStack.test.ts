import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonStack from "@components/blocks/ButtonStack.astro";

test("ButtonStack defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonStack, {
    slots: {
      default: "chickens",
    },
  });

  // expect(result).toMatchSnapshot();
});
