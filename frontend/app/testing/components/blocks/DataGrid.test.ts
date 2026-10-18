import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import DataGrid from "@components/blocks/DataGrid.astro";

const render = async (props: Record<string, unknown>) => {
  const container = await AstroContainer.create();
  return container.renderToString(DataGrid, {
    props: { columns: ["Pilot", "Kills"], template: "1fr 4rem", ...props },
    slots: {
      default:
        '<div class="data-grid-row" role="row"><span role="cell">A</span><span role="cell" data-label="Kills">3</span></div>',
    },
  });
};

test("header row, numeric columns and the shared template", async () => {
  const result = await render({ numeric: [1], min_width: "20rem" });

  expect(result).toContain('role="table"');
  expect(result.match(/role="columnheader"/g)).toHaveLength(2);
  expect(result).toMatch(/class="data-grid-numeric"[^>]*>Kills</);
  expect(result).toContain("--data_grid_template: 1fr 4rem");
  expect(result).toContain("min-width: 20rem");
  expect(result).toContain("data-grid--compact");
  expect(result).not.toContain("data-grid--stack");
});

test("ledger variant and stacked phone layout are opt-in classes", async () => {
  const result = await render({ variant: "ledger", stack: true });

  expect(result).toContain("data-grid--ledger");
  expect(result).toContain("data-grid--stack");
  expect(result).toContain('data-label="Kills"');
});
