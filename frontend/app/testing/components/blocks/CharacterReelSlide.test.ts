import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CharacterReelSlide from "@components/blocks/CharacterReelSlide.astro";

test("CharacterReelSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterReelSlide, {
    slots: {
      default: "slot mock",
    },
  });

  // expect(result).toMatchSnapshot();
});
