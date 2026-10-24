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

test("same-page hash links are followed on click", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(SectionTabs, {
    props: { tabs, aria_label: "Campaign", id_prefix: "campaign" },
  });

  // ClientRouter navigates #hash links with pushState, so no hashchange fires.
  expect(result).toContain('x-on:click.window="follow_link($event)"');
  expect(result).toContain("a[href^=");
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

test("an icon tab keeps its label for screen readers", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(SectionTabs, {
    props: {
      tabs: [...tabs, { id: "settings", label: "Settings", icon: "cog" }],
      aria_label: "Fleet",
      id_prefix: "fleet",
    },
  });

  expect(result).toContain("section-tab--icon");
  expect(result).toContain('title="Settings"');
  expect(result).toMatch(/visually-hidden[^>]*>Settings</);
});
