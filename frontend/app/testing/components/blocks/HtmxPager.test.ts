import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import HtmxPager from "@components/blocks/HtmxPager.astro";

const url_for = (page: number) => `/partials/list?page=${page}`;

const render = async (props: Record<string, unknown>, slots = {}) => {
  const container = await AstroContainer.create();
  return container.renderToString(HtmxPager, {
    props: { url_for, target: "#list", ...props },
    slots,
  });
};

const buttons = (html: string) => html.match(/<button[^>]*>/g) ?? [];

test("total_pages: first page disables Previous", async () => {
  const result = await render({ page: 1, total_pages: 3 });
  const [prev, next] = buttons(result);

  // Button renders `disabled` until Alpine starts; aria-disabled marks the real state.
  expect(prev).toContain('aria-disabled="true"');
  expect(next).not.toContain("aria-disabled");
  expect(next).toContain('hx-get="/partials/list?page=2"');
  expect(next).toContain('hx-target="#list"');
  expect(next).toContain('hx-indicator=".loader"');
  expect(result).toContain("Page 1");
});

test("total_pages: middle page enables both", async () => {
  const result = await render({ page: 2, total_pages: 3 });
  const [prev, next] = buttons(result);

  expect(prev).not.toContain("aria-disabled");
  expect(prev).toContain('hx-get="/partials/list?page=1"');
  expect(next).toContain('hx-get="/partials/list?page=3"');
});

test("total_pages: last page disables Next", async () => {
  const result = await render({ page: 3, total_pages: 3 });
  expect(buttons(result)[1]).toContain('aria-disabled="true"');
});

test("total_pages: one page keeps the status and actions, no buttons", async () => {
  const result = await render(
    { page: 1, total_pages: 1 },
    { status: "<span>1–4 / 4</span>", actions: "<a href='/x.csv'>Export</a>" },
  );

  expect(buttons(result)).toHaveLength(0);
  expect(result).toContain("1–4 / 4");
  expect(result).toContain("Export");
});

test("request attributes reach every button and win over target", async () => {
  const result = await render({
    page: 2,
    total_pages: 3,
    request: { "hx-target": "#body", "hx-include": "#filters" },
  });

  for (const button of buttons(result)) {
    expect(button).toContain('hx-target="#body"');
    expect(button).toContain('hx-include="#filters"');
  }
});

test("has_more: lone first page renders nothing", async () => {
  const result = await render({ page: 1, has_more: false });
  expect(result).not.toContain("htmx-pager");
});

test("has_more: Newer and Older around the page number", async () => {
  const result = await render({ page: 2, has_more: true });
  const [newer, older] = buttons(result);

  expect(newer).toContain('hx-get="/partials/list?page=1"');
  expect(older).toContain('hx-get="/partials/list?page=3"');
  expect(result).toContain("Newer");
  expect(result).toContain("Older");
  expect(result).toContain("Page 2");
});
