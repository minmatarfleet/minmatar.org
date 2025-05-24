import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CharacterFinder from "@components/blocks/CharacterFinder.astro";

test("CharacterFinder defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterFinder, {});

  expect(result).toMatchSnapshot();
});
