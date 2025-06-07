import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonCeoToken from "@components/blocks/ButtonCeoToken.astro";

test("ButtonCeoToken defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonCeoToken, {
    props: {
      corporation: {
        alliance_id: 12,
        coporation_id: 32,
        alliance_name: "Chickens R Us",
        corporation_name: "Top Cluck",
        corporation_type: "feathered",
        biography: "lorem ipsum chickensum",
        introduction: "in a world... with chickens",
        requirements: "must be a chicken",
        timezones: "CHICKUTC",
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
