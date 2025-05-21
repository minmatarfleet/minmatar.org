import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonCard from "@components/blocks/ButtonCard.astro";

test("ButtonCard defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonCard, {
    props: {
      title: "chickens rule the world",
      href: "chickens.com",
    },
  });

  expect(result).toMatchSnapshot();
});
