import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import OrderDetailHeader from "@components/blocks/industry/OrderDetailHeader.astro";

const render_header = async (props: Record<string, unknown>) => {
  const container = await AstroContainer.create();
  return container.renderToString(OrderDetailHeader, {
    props: {
      order_id: 9,
      character_id: 1,
      character_name: "Pilot",
      location_name: "Amamake",
      ...props,
    },
  });
};

test("a provisional order tells pilots to claim until it starts", async () => {
  const starts_at = new Date(Date.now() + 36 * 60 * 60 * 1000).toISOString();
  const html = await render_header({
    provisional: true,
    starts_at,
    started_at: null,
    fulfilled: false,
    unfulfilled_items: [],
    can_import: false,
  });

  expect(html).toContain("Claim quantities until");
  expect(html).toContain("Build at Amamake.");
  expect(html).not.toContain("Claiming has ended");
});

test("a started order lists unclaimed lines for the manager to import", async () => {
  const html = await render_header({
    provisional: false,
    starts_at: "2026-11-17T12:00:00Z",
    started_at: "2026-11-17T12:01:00Z",
    fulfilled: false,
    can_import: true,
    unfulfilled_items: [
      {
        id: 1,
        eve_type_id: 11985,
        eve_type_name: "Guardian",
        quantity: 100,
        imported_order_id: null,
      },
      {
        id: 2,
        eve_type_id: 587,
        eve_type_name: "Rifter",
        quantity: 10,
        imported_order_id: 44,
      },
    ],
  });

  expect(html).toContain("Start immediately at Amamake.");
  expect(html).toContain("100× Guardian");
  expect(html).not.toContain("10× Rifter");
  expect(html).toContain("/industry/orders/create/?import_unfulfilled=9");
});
