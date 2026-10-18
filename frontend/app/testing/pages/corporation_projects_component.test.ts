// @vitest-environment node
// (happy-dom drops the Cookie header from Request, and the partial reads auth_token from it.)
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";

const get_corporation_projects = vi.fn();
vi.mock("@helpers/api.minmatar.org/corporations", async (original) => ({
  ...(await original<typeof import("@helpers/api.minmatar.org/corporations")>()),
  get_corporation_projects: (...args: unknown[]) => get_corporation_projects(...args),
}));

import CorporationProjects from "@/pages/partials/corporation_projects_component.astro";

const SLUG = "minmatar-fleet";
const URL_BASE = "http://localhost:4321/partials/corporation_projects_component/?corporation_id=98000001&corporation=__SLUG__";

async function render(slug: string) {
  const container = await AstroContainer.create();
  return container.renderToString(CorporationProjects, {
    request: new Request(URL_BASE.replace("__SLUG__", slug), { headers: { cookie: "auth_token=token" } }),
  });
}


test("an API error renders ErrorRefetch instead of failing the partial", async () => {
  get_corporation_projects.mockImplementation(async () => {
    throw new Error("GET /corporations/98000001/projects: 502", { cause: 502 });
  });
  const html = await render(SLUG);

  expect(html).toContain("GET /corporations/98000001/projects: 502");
  expect(html).not.toContain('id="corporation-projects"');
});

test("a network failure renders ErrorRefetch that retries this partial", async () => {
  get_corporation_projects.mockImplementation(async () => {
    throw new TypeError("fetch failed");
  });
  const html = await render(SLUG);

  expect(html).toContain("fetch failed");
  expect(html).toMatch(/hx-get="[^"]*\/partials\/corporation_projects_component\/\?corporation_id=98000001[^"]*&delay=/);
  expect(html).not.toContain('id="corporation-projects"');
});

test("no projects renders the shared EmptyState", async () => {
  get_corporation_projects.mockResolvedValue({
    projects: [], campaigns: [], synced_at: null, refreshing: false, can_manage: false, has_token: true,
  });
  const html = await render(SLUG);

  expect(html).toContain('id="corporation-projects"');
  expect(html).toMatch(/<p class="\[ empty-state \]"[^>]*>[^<]+<\/p>/);
});
