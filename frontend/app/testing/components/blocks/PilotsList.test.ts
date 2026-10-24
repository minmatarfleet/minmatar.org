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

test("PilotsList shows scope groups as tags and names each row's actions menu", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(PilotsList, {
    props: {
      readonly: false,
      pilots: [
        {
          character_id: 1, character_name: "Alt One", is_primary: false, corp_id: 2, corp_name: "Rattini Tribe",
          alliance_id: null, alliance_name: null, esi_token: "Basic", token_status: "SUSPENDED", flags: ["NO_TAGS"],
          actual_groups: ["Basic", "FactionWarfare"], role_titles: [],
        },
      ],
    },
  });

  expect(result).toContain("Token suspended");
  expect(result).toContain("Faction Warfare");
  expect(result).toContain("No roles yet");
  expect(result).toContain('aria-label="Actions for Alt One"');
});
