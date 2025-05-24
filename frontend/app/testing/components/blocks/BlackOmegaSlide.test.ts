import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BlackOmegaSlide from "@components/blocks/BlackOmegaSlide.astro";

test("BlackOmegaSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(BlackOmegaSlide, {
    props: {
      corporation: 5,
      is_user_corporation: true,
    },
  });

  expect(result).toMatchSnapshot();
});
