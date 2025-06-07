import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetsList from "@components/blocks/AssetsList.astro";

test("AssetsList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetsList, {
    props: {
      assets_locations: [
        {
          location_name: "chick fil a",
          assets: [
            {
              name: "eggs",
              count: 67,
            },
          ],
        },
      ],
    },
  });

  // expect(result).toMatchSnapshot();
});
