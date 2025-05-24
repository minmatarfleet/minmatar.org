import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AmarrInfo from "@components/blocks/AmarrInfo.astro";

test("AmarrInfo defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AmarrInfo, {});

  expect(result).toMatchSnapshot();
});
