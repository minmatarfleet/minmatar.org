import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import FittingBuyOrderActions from "@components/blocks/FittingBuyOrderActions.astro";

test("owner delete confirm is an htmx button, not a form", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(FittingBuyOrderActions, {
    props: {
      is_owner: true,
      show: true,
      partial_base: "/partials/fitting_buy_order_component?order_id=12",
    },
  });

  expect(result).toContain('hx-post="/partials/fitting_buy_order_component?order_id=12"');
  expect(result).toContain("hx-vals=");
  expect(result).toContain("delete_order");
  expect(result).toContain('hx-target="#fitting-buy-order"');
  expect(result).not.toMatch(/<form[\s>]/);
  expect(result).toContain('type="button"');
});
