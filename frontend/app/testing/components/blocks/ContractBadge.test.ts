import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ContractBadge from "@components/blocks/ContractBadge.astro";

test("ContractBadge defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ContractBadge, {
    props: {
      contract: {
        current_quantity: 56,
        desired_quantity: 60,
        eve_type_id: 12,
        title: "MOOOOREEEE",
        trend_x_axis: [],
        trend_y_axis: [],
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
