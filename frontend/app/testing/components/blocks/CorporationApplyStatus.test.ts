import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationApplyStatus from "@components/blocks/CorporationApplyStatus.astro";

test("CorporationApplyStatus defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationApplyStatus, {
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
