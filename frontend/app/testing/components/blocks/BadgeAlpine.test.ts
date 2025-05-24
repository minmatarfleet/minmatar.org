import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BadgeAlpine from "@components/blocks/BadgeAlpine.astro";

test("BadgeAlpine defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(BadgeAlpine, {});

  expect(result).toMatchSnapshot();
});
