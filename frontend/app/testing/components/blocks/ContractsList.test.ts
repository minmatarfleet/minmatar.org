import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ContractsList from "@components/blocks/ContractsList.astro";

test("ContractsList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ContractsList, {
    props: {
      trade_hubs: [
        {
          name: "Roost",
          contract_groups: [
            {
              ship_type: "rifter",
              contracts: [],
            },
          ],
        },
      ],
      active_hub: "Roost",
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
