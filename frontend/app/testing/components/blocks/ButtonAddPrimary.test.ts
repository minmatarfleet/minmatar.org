import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonAddPrimary from "@components/blocks/ButtonAddPrimary.astro";

test("ButtonAddPrimary looks up show_alert_dialog on body", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonAddPrimary, {
    props: {
      dialog_title: "Add a main character",
    },
    slots: {
      default: "Add main",
    },
  });

  expect(result).toContain("Alpine.$data(document.body)");
  expect(result).toContain("root_data.show_alert_dialog");
  expect(result).not.toMatch(/[^.]show_alert_dialog\(\{/);
});
