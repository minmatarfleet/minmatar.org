import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BallsDeepSlide from "@components/blocks/BallsDeepSlide.astro";

test("BallsDeepSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(BallsDeepSlide, {
    props: {
      corporation: {
        corporation_id: 5,
        corporation_name: "chicken attack",
      },
      is_user_corporation: true,
    },
  });

  // expect(result).toMatchSnapshot();
});
