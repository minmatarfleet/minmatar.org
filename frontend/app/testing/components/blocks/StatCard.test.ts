import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import StatCard from "@components/blocks/StatCard.astro";

test("label, value and hint props", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "Active", value: 12, hint: "Last 30 days" },
  });

  expect(result).toMatch(/stat-card__label[^>]*>Active</);
  expect(result).toMatch(/stat-card__value[^>]*>12</);
  expect(result).toMatch(/stat-card__hint[^>]*>Last 30 days</);
});

test("no hint line without a hint", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "Active", value: 0 },
  });

  expect(result).toMatch(/stat-card__value[^>]*>0</);
  expect(result).not.toContain("stat-card__hint");
});

test("value and hint slots carry markup", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "Stockpile" },
    slots: {
      value: '<span data-tippy-content="1.2 billion">1.2B ISK</span>',
      hint: '<span data-tippy-content="42">42 ISK</span>',
    },
  });

  expect(result).toContain('<span data-tippy-content="1.2 billion">1.2B ISK</span>');
  expect(result).toContain("stat-card__hint");
});

test("coming soon replaces the value", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "Tournaments", value: "9", coming_soon: true },
  });

  expect(result).toContain("stat-card--soon");
  expect(result).not.toContain("stat-card__value");
});

test("glass variant keeps the card hooks and renders the default slot as the value", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "ISK destroyed", variant: "glass", tone: "success" },
    slots: { default: "128b", icon: '<i class="ic"></i>' },
  });

  expect(result).toContain("card border light-transparency");
  expect(result).toContain("--stat-tone: var(--green)");
  expect(result).toContain("128b");
  expect(result).toContain('<i class="ic"></i>');
});

test("cell variant puts the value above the label", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(StatCard, {
    props: { label: "Kills", value: "9", variant: "cell", title: "nine" },
  });

  expect(result).toContain('title="nine"');
  expect(result.indexOf("9")).toBeLessThan(result.indexOf("Kills"));
});
