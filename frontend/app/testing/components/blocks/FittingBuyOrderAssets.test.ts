import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import FittingBuyOrderAssets from "@components/blocks/FittingBuyOrderAssets.astro";

test("FittingBuyOrderAssets keeps fitting-buy styles on the host page", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(FittingBuyOrderAssets);

  expect(result).toContain("<template>");
  expect(result).toContain("fitting-buy-steps");
  expect(result).toContain("fitting-buy-contract-prices");
});
