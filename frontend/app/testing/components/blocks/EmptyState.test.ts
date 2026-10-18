import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";
import EmptyState from "@components/blocks/EmptyState.astro";

test("plain empty state is one muted paragraph", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(EmptyState, {
    props: { title: "No pilots yet.", id: "pilots-empty", class: "extra" },
  });

  expect(result).toMatch(/^<p class="\[ empty-state \] extra" id="pilots-empty"[^>]*>No pilots yet\.<\/p>$/);
});

test("a hint switches to the prominent title + hint layout", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(EmptyState, {
    props: { title: "No coordinators yet", hint: "Volunteer to coordinate this order." },
  });

  expect(result).toContain("empty-state empty-state--prominent");
  expect(result).toMatch(/<p class="\[ empty-state__title \]"[^>]*>No coordinators yet<\/p>/);
  expect(result).toMatch(/<small class="\[ empty-state__hint \]"[^>]*>Volunteer to coordinate this order\.<\/small>/);
});

test("prominent without a hint, and an action slot", async () => {
  const container = await AstroContainer.create();
  const bare = await container.renderToString(EmptyState, { props: { title: "No options", prominent: true } });
  expect(bare).toContain("empty-state--prominent");
  expect(bare).not.toContain("empty-state__hint");

  const with_action = await container.renderToString(EmptyState, {
    props: { title: "No projects" },
    slots: { action: '<a href="/x">Add one</a>' },
  });
  expect(with_action).toContain("empty-state--prominent");
  expect(with_action).toContain('<a href="/x">Add one</a>');
});

test("styles ship globally so partials get them", () => {
  // htmx drops a partial's own <style>; EmptyState relies on base.scss instead.
  const base = readFileSync(join(__dirname, "../../../src/styles/base.scss"), "utf8");
  expect(base).toContain("@use 'components/empty-state';");
  const component = readFileSync(join(__dirname, "../../../src/components/blocks/EmptyState.astro"), "utf8");
  expect(component).not.toMatch(/^<style/m);
});
