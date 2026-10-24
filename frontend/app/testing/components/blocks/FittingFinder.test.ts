// @vitest-environment node
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";

const get_fittings = vi.fn();
vi.mock("@helpers/api.minmatar.org/ships", async (original) => ({
  ...(await original<typeof import("@helpers/api.minmatar.org/ships")>()),
  get_fittings: (...args: unknown[]) => get_fittings(...args),
}));

import FittingFinder from "@components/blocks/FittingFinder.astro";

// Every page renders the finder (Viewport). Inlining the fitting library here
// made each page ~640 KB of duplicate text that search engines would not index.
test("the finder renders without the fitting library and searches through its partial", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(FittingFinder, {
    request: new Request("http://localhost:4321/"),
  });

  expect(get_fittings).not.toHaveBeenCalled();
  expect(html).not.toContain("eft_format");
  expect(html).not.toContain('fitting-finder-action="accept"');
  expect(html).toMatch(/hx-get="\/partials\/fittings_finder_list_component"/);
  expect(html).toContain('hx-target="#fittings-finder-list"');
  expect(html).toContain('id="fittings-finder-list"');
  expect(html).toContain('name="search"');
});
