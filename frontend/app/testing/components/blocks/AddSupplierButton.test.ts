import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AddSupplierButton from "@components/blocks/AddSupplierButton.astro";

test("AddSupplierButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AddSupplierButton, {});

  // expect(result).toMatchSnapshot();
});
