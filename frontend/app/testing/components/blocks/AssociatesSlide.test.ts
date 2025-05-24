import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AssociatesSlide from "@components/blocks/AssociatesSlide.astro";

test("AssociatesSlide defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AssociatesSlide, {});

  expect(result).toMatchSnapshot();
});
