import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CopyToken from "@components/blocks/CopyToken.astro";

test("CopyToken defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CopyToken, {});

  expect(result).toMatchSnapshot();
});
