import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AllianceBento from "@components/blocks/AllianceBento.astro";

test("AllianceBento defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AllianceBento, {});

  expect(result).toMatchSnapshot();
});
