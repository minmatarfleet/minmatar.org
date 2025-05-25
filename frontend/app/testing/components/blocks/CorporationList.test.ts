import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationList from "@components/blocks/CorporationList.astro";

test("CorporationList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationList, {});

  expect(result).toMatchSnapshot();
});
