import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonAddPrimary from "@components/blocks/ButtonAddPrimary.astro";

test("ButtonAddPrimary defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonAddPrimary, {});

  expect(result).toMatchSnapshot();
});
