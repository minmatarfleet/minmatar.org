import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import PilotsList from "@components/blocks/PilotsList.astro";

test("PilotsList add-pilot looks up show_alert_dialog on body", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(PilotsList, {
    props: {
      readonly: false,
      pilots: [],
    },
  });

  expect(result).toContain("Alpine.$data(document.body)");
  expect(result).toContain("root_data.show_alert_dialog");
  expect(result).not.toMatch(/[^.]show_alert_dialog\(\{/);
});
