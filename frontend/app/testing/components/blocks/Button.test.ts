import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Button from "@components/blocks/Button.astro";

test("Button defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Button, {});

  expect(result).toMatchSnapshot();
});
