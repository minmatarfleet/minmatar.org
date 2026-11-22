import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CharacterPicture from "@components/blocks/CharacterPicture.astro";

import { get_player_icon } from "@helpers/eve_image";
vi.mock("@helpers/eve_image");

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

// Regression: a <button> picture nested in CollapsableButton / the SRP card makes
// the HTML parser close the outer button and pushes the rest of the markup out of
// its Alpine x-data scope ("expanded is not defined").
test("CharacterPicture never renders a nested <button> or <a>", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterPicture, {
    props: { character_id: 42, character_name: "chicklet" },
  });

  expect(result).not.toMatch(/<button\b/);
  expect(result).not.toMatch(/<a\b/);
  expect(result).toContain('role="button"');
  expect(result).toContain("x-on:keydown.enter.stop.prevent");
});
