import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonAuth from "@components/blocks/ButtonAuth.astro";

test("ButtonAuth defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonAuth, {});

  expect(result).toMatchSnapshot();
});
