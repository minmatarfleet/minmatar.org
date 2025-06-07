import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AllianceReel from "@components/blocks/AllianceReel.astro";

test("AllianceReel defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AllianceReel, {});

  // expect(result).toMatchSnapshot();
});
