import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetsListAlpine from "@components/blocks/AssetsListAlpine.astro";

test("AssetsListAlpine defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetsListAlpine, {});

  // expect(result).toMatchSnapshot();
});
