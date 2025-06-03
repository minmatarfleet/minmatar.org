import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BallsDeepSlide from "@components/blocks/BallsDeepSlide.astro";

test("BallsDeepSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(BallsDeepSlide, {
    props: {
      corporation: 5,
      is_user_corporation: true,
    },
  });

  // expect(result).toMatchSnapshot();
});
