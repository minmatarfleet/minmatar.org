import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetsBlockAlpine from "@components/blocks/AssetsBlockAlpine.astro";

test("AssetsBlockAlpine defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetsBlockAlpine, {});

  // expect(result).toMatchSnapshot();
});
