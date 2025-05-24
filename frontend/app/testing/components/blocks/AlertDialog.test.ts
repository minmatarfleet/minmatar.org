import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AlertDialog from "@components/blocks/AlertDialog.astro";

test("AlertDialog defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AlertDialog, {});

  expect(result).toMatchSnapshot();
});
