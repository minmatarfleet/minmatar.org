import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import ClipboardButton from "@components/blocks/ClipboardButton.astro";

test("ClipboardButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ClipboardButton, {
    props: {
      id: 56,
      alert_prefix: "what_the_cluck_",
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
