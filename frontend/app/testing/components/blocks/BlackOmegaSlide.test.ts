import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BlackOmegaSlide from "@components/blocks/BlackOmegaSlide.astro";

test("BlackOmegaSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(BlackOmegaSlide, {
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
