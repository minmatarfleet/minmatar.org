import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationSlideStatus from "@components/blocks/CorporationSlideStatus.astro";

test("CorporationSlideStatus defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationSlideStatus, {
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
