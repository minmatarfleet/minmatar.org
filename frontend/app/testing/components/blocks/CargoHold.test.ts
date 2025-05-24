import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CargoHold from "@components/blocks/CargoHold.astro";

test("CargoHold defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CargoHold, {
    props: {
      cargo: [
        {
          amont: 12,
          name: "chicken",
        },
      ],
    },
    slots: {
      default: "slot chickens",
    },
  });

  expect(result).toMatchSnapshot();
});
