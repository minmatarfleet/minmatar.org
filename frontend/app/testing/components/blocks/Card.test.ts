import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Card from "@components/blocks/Card.astro";

test("Card defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Card, {});

  expect(result).toMatchSnapshot();
});
