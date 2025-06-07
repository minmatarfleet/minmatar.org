import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CharacterPicture from "@components/blocks/CharacterPicture.astro";

import { get_player_icon } from "@helpers/eve_image_server";
vi.mock("@helpers/eve_image_server");

test("CharacterPicture defaults", async () => {
  vi.mocked(get_player_icon).mockImplementation((id, size) => {
    return "mock-picture-src";
  });

  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterPicture, {
    props: {
      character_id: 42,
      x_character_id: 765,
      character_name: "chicklet",
    },
  });

  // expect(result).toMatchSnapshot();
});
