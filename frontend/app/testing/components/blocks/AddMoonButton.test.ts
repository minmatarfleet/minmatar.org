import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AddMoonButton from "@components/blocks/AddMoonButton.astro";

test("AddMoonButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AddMoonButton, {});

  //expect(result).toMatchSnapshot();
});
