import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ConfirmDialog from "@components/blocks/ConfirmDialog.astro";

test("ConfirmDialog defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ConfirmDialog, {
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
