import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CharactersTagList from "@components/blocks/CharactersTagList.astro";

test("CharactersTagList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharactersTagList, {
    props: {
      tags: [
        {
          id: 4523,
          image_name: "some-image",
          description: "the sky is falling",
        },
      ],
      tags_summary: [
        {
          character_id: 18,
          tags: [],
        },
        {
          character_id: 2345,
          tags: [],
        },
      ],
      active_character: {
        character_id: 2345,
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
