// @vitest-environment node
// Node's Request keeps Referer; happy-dom drops it as a forbidden header.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";
import {
  is_htmx_request,
  login_redirect,
  login_return_url,
  partial_redirect,
} from "@helpers/http_responses";

const PARTIAL_URL =
  "http://localhost:4321/partials/fleet_role_item_component?fleet_id=7&role=dps";
const PAGE_URL = "http://localhost:4321/fleets/upcoming/7/?tab=roles";

function request(headers: Record<string, string> = {}, url = PARTIAL_URL) {
  return new Request(url, { headers });
}

function context(headers: Record<string, string> = {}, url = PARTIAL_URL) {
  return { request: request(headers, url), url: new URL(url) };
}

describe("is_htmx_request", () => {
  test("is true only for HX-Request: true", () => {
    expect(is_htmx_request(request({ "HX-Request": "true" }))).toBe(true);
    expect(is_htmx_request(request({ "HX-Request": "false" }))).toBe(false);
    expect(is_htmx_request(request())).toBe(false);
  });
});

describe("partial_redirect", () => {
  test("htmx request gets 200 with HX-Redirect and an empty body", async () => {
    const response = partial_redirect(
      request({ "HX-Request": "true" }),
      "/ships/srp/onboarding/",
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("HX-Redirect")).toBe("/ships/srp/onboarding/");
    expect(response.headers.get("Location")).toBeNull();
    expect(await response.text()).toBe("");
  });

  test("a direct request still gets a 302", () => {
    const response = partial_redirect(request(), "/ships/srp/onboarding/");

    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe("/ships/srp/onboarding/");
    expect(response.headers.get("HX-Redirect")).toBeNull();
  });
});

describe("login_return_url", () => {
  test("htmx request returns to the page, not the partial", () => {
    expect(
      login_return_url(
        request({ "HX-Request": "true", "HX-Current-URL": PAGE_URL }),
      ),
    ).toBe(PAGE_URL);
  });

  test("falls back to Referer, then to the request URL", () => {
    expect(
      login_return_url(request({ "HX-Request": "true", Referer: PAGE_URL })),
    ).toBe(PAGE_URL);
    expect(login_return_url(request({ "HX-Request": "true" }))).toBe(
      PARTIAL_URL,
    );
  });

  test("a direct request returns to its own URL", () => {
    expect(login_return_url(request({ Referer: PAGE_URL }))).toBe(PARTIAL_URL);
  });
});

describe("login_redirect", () => {
  test("htmx request navigates the window to auth_init with the page URL encoded", () => {
    const response = login_redirect(
      context({ "HX-Request": "true", "HX-Current-URL": PAGE_URL }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("HX-Redirect")).toBe(
      `/redirects/auth_init?redirect_url=${encodeURIComponent(PAGE_URL)}`,
    );
  });

  test("a direct request gets a 302 back to the partial URL, encoded", () => {
    const response = login_redirect(context());
    const location = response.headers.get("Location") ?? "";

    expect(response.status).toBe(302);
    expect(location).toBe(
      `/redirects/auth_init?redirect_url=${encodeURIComponent(PARTIAL_URL)}`,
    );
    // The query string of the return URL must not leak into auth_init's own.
    expect(new URL(location, PARTIAL_URL).searchParams.get("role")).toBeNull();
    expect(
      new URL(location, PARTIAL_URL).searchParams.get("redirect_url"),
    ).toBe(PARTIAL_URL);
  });
});

test("partials redirect through partial_redirect / login_redirect, never Astro.redirect", () => {
  const partials_dir = join(
    dirname(fileURLToPath(import.meta.url)),
    "../../src/pages/partials",
  );
  const offenders = readdirSync(partials_dir)
    .filter((name) => name.endsWith(".astro"))
    .filter((name) =>
      readFileSync(join(partials_dir, name), "utf8").includes("Astro.redirect("),
    );

  expect(offenders).toEqual([]);
});
