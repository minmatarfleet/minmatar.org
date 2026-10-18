import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import FilterChip from "@components/blocks/FilterChip.astro";
import ChipGroup from "@components/blocks/ChipGroup.astro";

test("button chip reports its state with aria-pressed", async () => {
  const container = await AstroContainer.create();
  const off = await container.renderToString(FilterChip, { slots: { default: "All" } });
  const on = await container.renderToString(FilterChip, {
    props: { active: true },
    slots: { default: "All" },
  });

  expect(off).toMatch(/<button type="button"[^>]*aria-pressed="false"/);
  expect(off).not.toContain("is-active");
  expect(on).toContain('aria-pressed="true"');
  expect(on).toContain("is-active");
});

test("Alpine bindings pass through to the button", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(FilterChip, {
    props: {
      "x-on:click": "set_category('fw')",
      "x-bind:class": "category === 'fw' && 'is-active'",
    },
    slots: { default: "FW" },
  });

  expect(result).toContain(`x-on:click="set_category('fw')"`);
  expect(result).toContain("x-bind:class=");
});

test("link chip marks the current view with aria-current, not aria-pressed", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(FilterChip, {
    props: { href: "/market/fitting_orders/?mine=1", active: true },
    slots: { default: "Mine" },
  });

  expect(result).toMatch(/<a href="\/market\/fitting_orders\/\?mine=1"/);
  expect(result).toContain('aria-current="page"');
  expect(result).not.toContain("aria-pressed");
});

test("chip group is a labelled group that scrolls unless it wraps", async () => {
  const container = await AstroContainer.create();
  const scrolling = await container.renderToString(ChipGroup, {
    props: { aria_label: "Category" },
    slots: { default: "<button>All</button>" },
  });
  const wrapping = await container.renderToString(ChipGroup, {
    props: { wrap: true },
    slots: { default: "<button>All</button>" },
  });

  expect(scrolling).toContain('role="group"');
  expect(scrolling).toContain('aria-label="Category"');
  expect(scrolling).toContain("xfade-scroll");
  expect(wrapping).toContain("chip-group--wrap");
  expect(wrapping).not.toContain("xfade-scroll");
});
