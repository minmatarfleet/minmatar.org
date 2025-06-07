import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationStatus from "@components/blocks/CorporationStatus.astro";

test("CorporationStatus defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationStatus, {
    props: {
      corporation: {
        corporation_id: 87,
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
