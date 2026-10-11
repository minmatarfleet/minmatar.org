import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import StartFleet from "@components/blocks/StartFleet.astro";
import type { SummaryCharacter } from "@dtypes/api.minmatar.org";

const pilots: SummaryCharacter[] = [
  {
    character_id: 1,
    character_name: "Test Pilot",
    is_primary: true,
    corp_id: 1000009,
    corp_name: "Test Corp",
    alliance_id: 1,
    alliance_name: "Test Alliance",
    esi_token: "",
    token_status: "ACTIVE",
    flags: [],
    requested_groups: [],
    actual_groups: [],
  },
];

test("StartFleet posts the start partial in-page via htmx", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StartFleet, {
    props: { pilots },
  });

  expect(result).toContain('hx-post="/partials/fleet_start_component/"');
  expect(result).toContain('hx-target="#fleet-start"');
  expect(result).toContain('hx-swap="innerHTML"');
  expect(result).toContain('name="fc_character_id"');
});
