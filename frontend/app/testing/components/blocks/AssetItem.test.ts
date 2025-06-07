import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetItem from "@components/blocks/AssetItem.astro";

test("AssetItem defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetItem, {
    props: {
      asset: {
        id: 91,
        name: "chicken feed",
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
