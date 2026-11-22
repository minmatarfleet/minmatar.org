import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonViewHealthChartData from "@components/blocks/ButtonViewHealthChartData.astro";

const history = [
  { captured_at: "2026-11-02T10:00:00Z", contracts_health_pct: 80, contracts_viability_pct: 70, sell_orders_health_pct: 50, sell_orders_viability_pct: 40 },
  { captured_at: "2026-11-01T10:00:00Z", contracts_health_pct: 75, contracts_viability_pct: 70, sell_orders_health_pct: 50, sell_orders_viability_pct: 40 },
];

test("ButtonViewHealthChartData lists the plot points in a DataTable, oldest first, with deltas", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonViewHealthChartData, {
    props: { history, type: "contracts", coverage_tone: "good", viability_tone: "warn" },
  });

  expect(result).toContain("data-table");
  expect(result).toContain('scope="col"');
  expect(result).toContain("--coverage_color: var(--green)");
  expect(result).toContain("80.00");
  expect(result).toContain("75.00");
  // 75 -> 80 is up by 5, rendered once as a green delta.
  expect(result).toContain("text-green");
  expect(result.indexOf("75.00")).toBeLessThan(result.indexOf("80.00"));
});
