import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CharacterLinks from "@components/blocks/CharacterLinks.astro";

test("CharacterLinks defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterLinks, {
    props: {
      character_id: 56,
    },
  });

  // expect(result).toMatchSnapshot();
});
