import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import OrderBreakdown from "@components/blocks/OrderBreakdown.astro";

test("order breakdown rebinds Alpine after outerHTML delivery swaps", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(OrderBreakdown, {
    props: {
      order_id: 46,
      primary_character_id: 95434311,
      order_breakdown: [
        {
          id: 141,
          eve_type_id: 17703,
          eve_type_name: "Tempest Fleet Issue",
          quantity: 50,
          unassigned_quantity: 0,
          self_assign_maximum: null,
          self_assign_window_ends_at: new Date("2026-08-31T15:15:35.283Z"),
          target_unit_price: null,
          target_estimated_margin: null,
          assignments: [
            {
              id: 286,
              character_id: 95434311,
              character_name: "Jyll Ataru",
              quantity: 10,
              target_unit_price: null,
              target_estimated_margin: null,
              delivered_quantity: 10,
              delivered_at: new Date("2026-08-30T00:31:56.451Z"),
              has_blueprints: false,
            },
          ],
        },
      ],
      location_name: undefined,
      swap_target_id: "order-breakdown-46-inner",
      claim_render: "breakdown",
    },
  });

  expect(result).toContain('id="order-breakdown-46-inner"');
  expect(result).toContain(
    'hx-on--after-swap="window.minmatar_after_outer_html_swap?.call(this)"',
  );
  expect(result).toContain("delivery=false");
  expect(result).not.toMatch(/hx-on=["']htmx:afterSwap:/);
});
