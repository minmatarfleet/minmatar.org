import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CancelFleetButton from "@components/blocks/CancelFleetButton.astro";

test("CancelFleetButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CancelFleetButton, {
    props: {
      fleet_id: 91234,
    },
  });

  expect(result).toMatchSnapshot();
});
