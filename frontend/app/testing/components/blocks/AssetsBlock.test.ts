import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssetsBlock from "@components/blocks/AssetsBlock.astro";

test("AssetsBlock defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssetsBlock, {
    props: {
      assets_location: {
        location_name: "coop",
        assets: [
          {
            count: 5,
            name: "chickens",
          },
        ],
      },
    },
  });

  expect(result).toMatchSnapshot();
});
