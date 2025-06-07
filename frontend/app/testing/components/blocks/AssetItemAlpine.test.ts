import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetItemAlpine from "@components/blocks/AssetItemAlpine.astro";

test("AssetItemAlpine defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetItemAlpine, {});

  // expect(result).toMatchSnapshot();
});
