import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationFinder from "@components/blocks/CorporationFinder.astro";

test("CorporationFinder defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationFinder, {});

  expect(result).toMatchSnapshot();
});
