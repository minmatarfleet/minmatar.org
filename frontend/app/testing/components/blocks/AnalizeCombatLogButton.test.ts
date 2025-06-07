import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AnalizeCombatLogButton from "@components/blocks/AnalizeCombatLogButton.astro";

test("AnalizeCombatLogButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AnalizeCombatLogButton, {});

  // expect(result).toMatchSnapshot();
});
