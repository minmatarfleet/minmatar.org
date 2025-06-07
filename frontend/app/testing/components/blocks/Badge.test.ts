import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Badge from "@components/blocks/Badge.astro";

test("Badge defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Badge, {});

  // expect(result).toMatchSnapshot();
});
