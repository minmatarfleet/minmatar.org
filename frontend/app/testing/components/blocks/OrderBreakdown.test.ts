import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import OrderBreakdown from "@components/blocks/OrderBreakdown.astro";

test("order breakdown leaves outerHTML swap re-init to the global hook", async () => {
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
          estimated_profit_per_unit: null,
          assignments: [
            {
              id: 286,
              character_id: 95434311,
              character_name: "Jyll Ataru",
              quantity: 10,
              target_unit_price: null,
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
  // htmx processes the replacement, Alpine's observer initialises it, and the
  // teleported Actions panel processes itself (Dropdown x-init). A per-node
  // after-swap hook would re-process it and could re-fire load triggers.
  expect(result).not.toContain("minmatar_after_outer_html_swap");
  expect(result).toContain("delivery=false");
  expect(result).not.toMatch(/hx-on=["']htmx:afterSwap:/);
});

const item = (overrides: Record<string, unknown> = {}) => ({
  id: 141,
  eve_type_id: 17703,
  eve_type_name: "Tempest Fleet Issue",
  quantity: 50,
  unassigned_quantity: 40,
  self_assign_maximum: null,
  self_assign_window_ends_at: new Date("2026-08-31T15:15:35.283Z"),
  target_unit_price: null,
  estimated_profit_per_unit: null,
  assignments: [],
  ...overrides,
});

const render_breakdown = async (props: Record<string, unknown>) => {
  const container = await AstroContainer.create();
  return container.renderToString(OrderBreakdown, {
    props: { order_id: 46, primary_character_id: 95434311, location_name: undefined, ...props },
  });
};

test("item actions are an ActionMenu: claim and blueprints as hosts, planner link", async () => {
  const result = await render_breakdown({ order_breakdown: [item()] });

  expect(result).toContain("action-menu__list");
  expect(result.match(/\[ action-menu-item-host \]/g)).toHaveLength(2);
  // An unclaimed item's Claim keeps the green of the old claim button.
  expect(result).toContain("action-menu-item-host--success");
  expect(result).toContain("/industry/orders/planner?order_id=46&#38;item_id=141");
  expect(result).not.toContain("delivery=false");
});

test("a delivered claim reverts through a two-step confirm item", async () => {
  const delivered = item({
    unassigned_quantity: 0,
    assignments: [{
      id: 286,
      character_id: 95434311,
      character_name: "Jyll Ataru",
      quantity: 10,
      target_unit_price: null,
      delivered_quantity: 10,
      delivered_at: new Date("2026-08-30T00:31:56.451Z"),
      has_blueprints: false,
    }],
  });
  const result = await render_breakdown({ order_breakdown: [delivered] });

  const armed = result.match(/<button[^>]*is-confirm[^>]*>/g) ?? [];
  expect(armed).toHaveLength(1);
  expect(armed[0]).toContain("hx-patch=");
  expect(armed[0]).toContain("delivery=false");
  expect(result).not.toMatch(/<button[^>]*x-show="!confirming"[^>]*hx-patch/);
});

test("a blocked claim is a disabled item with the reason as its tooltip", async () => {
  const result = await render_breakdown({
    order_breakdown: [item()],
    claim_disabled_reason: "Add your blueprints first",
  });

  expect(result).toContain('data-tippy-content="Add your blueprints first"');
  expect(result).toMatch(/<button[^>]*action-menu-item--success[^>]*disabled/);
  expect(result.match(/\[ action-menu-item-host \]/g)).toHaveLength(1);
});
