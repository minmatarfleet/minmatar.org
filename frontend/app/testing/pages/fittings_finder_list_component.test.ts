// @vitest-environment node
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeEach, expect, test, vi } from "vitest";

const get_fittings = vi.fn();
vi.mock("@helpers/api.minmatar.org/ships", async (original) => ({
  ...(await original<typeof import("@helpers/api.minmatar.org/ships")>()),
  get_fittings: (...args: unknown[]) => get_fittings(...args),
}));

// get_fitting_item reads the SDE for the hull type; the partial only needs these fields.
const SHIP_TYPES: Record<number, string> = { 587: "Frigate", 645: "Battleship", 22442: "Command Ship" };
vi.mock("@helpers/fetching/ships", async (original) => ({
  ...(await original<typeof import("@helpers/fetching/ships")>()),
  get_fitting_item: async (fitting: { id: number; name: string; ship_id: number }) => ({
    id: fitting.id,
    fitting_name: fitting.name,
    ship_id: fitting.ship_id,
    ship_type: SHIP_TYPES[fitting.ship_id],
  }),
}));

import FittingsFinderList from "@/pages/partials/fittings_finder_list_component.astro";
import { SHIP_TYPES_SORTED } from "@helpers/eve";

const FITTINGS = [
  { id: 3, name: "[FL33T] Dominix", ship_id: 645 },
  { id: 1, name: "[NVY] Shield Rifter", ship_id: 587 },
  { id: 2, name: "[FL33T] Rifter", ship_id: 587 },
  { id: 4, name: "[FL33T] Sleipnir", ship_id: 22442 },
];

async function render(search: string | null) {
  const container = await AstroContainer.create();
  const query = search === null ? "" : `?search=${encodeURIComponent(search)}`;
  return container.renderToString(FittingsFinderList, {
    request: new Request(`http://localhost:4321/partials/fittings_finder_list_component${query}`),
  });
}

const result_ids = (html: string) =>
  [...html.matchAll(/fitting-finder-data="(\d+)"/g)].map((match) => Number(match[1]));

beforeEach(() => {
  get_fittings.mockReset();
  get_fittings.mockResolvedValue(FITTINGS);
});

test("an empty search renders nothing and skips the API", async () => {
  const html = await render(null);

  expect(result_ids(html)).toEqual([]);
  expect(html).not.toContain("No fittings found");
  expect(html).not.toContain("flex-block");
  expect(get_fittings).not.toHaveBeenCalled();
});

test("matches fitting names case-insensitively", async () => {
  const html = await render("RIFTER");

  expect(result_ids(html)).toEqual([1, 2]);
});

test("orders results by hull class like the old inline list", async () => {
  const html = await render("[fl33t]");
  const by_class = [3, 2, 4].sort(
    (a, b) =>
      SHIP_TYPES_SORTED.indexOf(SHIP_TYPES[FITTINGS.find((f) => f.id === a)!.ship_id]) -
      SHIP_TYPES_SORTED.indexOf(SHIP_TYPES[FITTINGS.find((f) => f.id === b)!.ship_id]),
  );

  expect(result_ids(html)).toEqual(by_class);
  expect(by_class).not.toEqual([3, 2, 4]);
});

test("results keep the finder's accept hooks and link to the named fitting URL", async () => {
  const html = await render("sleip");

  expect(result_ids(html)).toEqual([4]);
  expect(html).toContain('fitting-finder-action="accept"');
  expect(html).toContain('x-on:click="(search = \'\')"');
  expect(html).toContain('href="/ships/fittings/normal/4-fl33t-sleipnir/"');
  expect(html).toContain("[FL33T] Sleipnir");
  expect(html).toContain("Command Ship");
  // The message stays first but hidden, like the old inline list, so results keep their spacing.
  expect(html).toMatch(/<div[^>]*hidden[^>]*>\s*<span>No fittings found<\/span>/);
});

test("no match renders the no-fittings message", async () => {
  const html = await render("nyx");

  expect(result_ids(html)).toEqual([]);
  expect(html).toMatch(/<div class="\[ py-\[var\(--space-2xs\)\] px-\[var\(--space-2xs\)\] \]"[^>]*>\s*<span>No fittings found<\/span>/);
  expect(html).not.toMatch(/<div[^>]*hidden[^>]*>\s*<span>No fittings found/);
});

test("an API error renders ErrorRefetch that retries the same search", async () => {
  get_fittings.mockRejectedValue(new Error("GET /fittings: 502"));
  const html = await render("rifter");

  expect(html).toContain("GET /fittings: 502");
  expect(html).toMatch(/hx-get="[^"]*\/partials\/fittings_finder_list_component\?search=rifter/);
});
