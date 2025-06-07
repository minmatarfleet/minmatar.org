import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AllianceFinder from "@components/blocks/AllianceFinder.astro";

test("AllianceFinder defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AllianceFinder, {});

  // expect(result).toMatchSnapshot();
});
