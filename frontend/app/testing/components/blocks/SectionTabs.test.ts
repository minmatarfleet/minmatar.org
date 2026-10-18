import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import SectionTabs from "@components/blocks/SectionTabs.astro";

const tabs = [
  { id: "systems", label: "Systems" },
  { id: "fleets", label: "Fleets" },
];

test("one hashchange listener, wired to follow_hash", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(SectionTabs, {
    props: { tabs, aria_label: "Campaign", id_prefix: "campaign" },
  });

  // A second x-on:hashchange attribute is dropped by the HTML parser.
  expect(result.match(/x-on:hashchange\.window=/g)).toHaveLength(1);
  expect(result).toContain('x-on:hashchange.window="follow_hash()"');
  expect(result).toContain('id="campaign-tab-systems"');
  expect(result).toContain('aria-controls="campaign-panel-fleets"');
});

test("hash aliases reach the tab state", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(SectionTabs, {
    props: {
      tabs,
      aria_label: "Campaign",
      id_prefix: "campaign",
      hash_aliases: { "campaign-system-": "systems" },
    },
  });

  expect(result).toContain("campaign-system-");
  expect(result).toContain("tab_for(hash)");
});
