import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetLocationItem from "@components/blocks/AssetLocationItem.astro";

test("AssetLocationItem defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetLocationItem, {
    props: {
      asset_location: {
        location_name: "chick fil a",
        assets_count: 9871,
      },
    },
  });

  expect(result).toMatchSnapshot();
});
