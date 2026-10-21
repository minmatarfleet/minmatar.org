import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import BuybackPurchaseOrderItem from "@components/blocks/BuybackPurchaseOrderItem.astro";
import type { BuybackPurchaseOrder } from "@dtypes/api.minmatar.org";

const order = (overrides: Partial<BuybackPurchaseOrder> = {}): BuybackPurchaseOrder => ({
  id: 31,
  status: "pending",
  source: "web",
  created_by_user_id: 4,
  character_id: 95434311,
  character_name: "Jyll Ataru",
  contract_total: 125000000,
  sell_price_basis: "jita_buy",
  sell_markup: 0,
  janice_tsv: "Tritanium\t1000",
  created_at: "2026-10-18T12:00:00Z",
  completed_at: null,
  discord_thread_id: 1,
  discord_thread_url: "https://discord.com/channels/1/2/3",
  lines: [{ type_id: 34, name: "Tritanium", quantity: 1000, unit_price: 5, line_total: 5000, fill_source: "stock" }],
  ...overrides,
});

const render = async (props: Record<string, unknown>) => {
  const container = await AstroContainer.create();
  return container.renderToString(BuybackPurchaseOrderItem, { props });
};

test("pending order actions are an ActionMenu with copy, thread and confirm items", async () => {
  const result = await render({ order: order(), can_manage: true });

  expect(result).toContain("action-menu--fill");
  expect(result).toContain("action-menu--fit");
  expect(result).toContain("copyFitToClipboard('buyback-order-isk-31')");
  expect(result).toContain("copyFitToClipboard('buyback-order-janice-31')");
  expect(result).toContain('id="buyback-order-isk-31"');
  expect(result).toContain('id="buyback-order-janice-31"');
  expect(result).toMatch(/<a href="https:\/\/discord\.com\/channels\/1\/2\/3"[^>]*target="_blank"/);

  // Complete and cancel are two-step: only the armed button submits its form.
  expect(result).toContain('name="action" value="complete"');
  expect(result).toContain('name="action" value="cancel"');
  expect(result.match(/<button type="submit"[^>]*is-confirm/g)).toHaveLength(2);
  expect(result).toContain("action-menu-item--success");
  expect(result).toContain("action-menu-item--danger");
});

test("pilots without manage rights can cancel but not complete", async () => {
  const result = await render({ order: order(), can_manage: false });

  expect(result).toContain('value="cancel"');
  expect(result).not.toContain('value="complete"');
});

test("a settled order without a thread or Janice export has no menu", async () => {
  const result = await render({
    order: order({ status: "completed", janice_tsv: "", discord_thread_url: null }),
    can_manage: true,
  });

  expect(result).not.toContain("action-menu");
  expect(result).not.toContain("buyback-order-isk-31");
});
