import { afterEach, describe, expect, test, vi } from "vitest";
import {
  PARTIAL_STYLE_ATTRIBUTE,
  apply_partial_stylesheets,
  bind_partial_styles,
  extract_partial_stylesheets,
  htmx_drops_stylesheets,
  missing_rules_css,
  rule_keys,
} from "@helpers/htmx_partial_styles";

// What an Astro partial response looks like: stylesheet tags first, which
// DOMParser hoists into <head>, then the markup htmx swaps in.
const PARTIAL = `<!DOCTYPE html><link rel="stylesheet" href="/_astro/picker.css"><style>.pick-ships__rows[data-astro-cid-p1]{display:flex}.flex-block{display:flex}@media (min-width: 40em){.pick-ships__row[data-astro-cid-p1]{display:grid}.flex-block{gap:1px}}</style><div class="pick-ships__rows" data-astro-cid-p1>rows</div>`;

// happy-dom would otherwise try to download every <link> stylesheet it parses.
(window as any).happyDOM.settings.disableCSSFileLoading = true;

const rule = (cssText: string) => ({ cssText });
const media = (prelude: string, inner: string[]) => ({
  cssText: `${prelude} { ${inner.join(" ")} }`,
  cssRules: inner.map(rule),
});

afterEach(() => {
  document.head.innerHTML = "";
  document.body.innerHTML = "";
});

describe("extract_partial_stylesheets", () => {
  test("finds the link and style that htmx would drop", () => {
    const sheets = extract_partial_stylesheets(PARTIAL, "http://localhost:4321/fleets/");

    expect(sheets.map((s) => s.href ?? "style")).toEqual([
      "http://localhost:4321/_astro/picker.css",
      "style",
    ]);
    expect(sheets[1].css).toContain(".pick-ships__rows");
  });

  test("leaves responses alone when htmx keeps their styles (first tag is <style>)", () => {
    expect(htmx_drops_stylesheets("<!DOCTYPE html><style>.a{}</style><div></div>")).toBe(false);
    expect(htmx_drops_stylesheets('<!DOCTYPE html><link rel="stylesheet" href="/a.css"><div></div>')).toBe(true);
    expect(
      extract_partial_stylesheets('<!DOCTYPE html><style>.a{}</style><link rel="stylesheet" href="/a.css"><div></div>', "http://x/"),
    ).toEqual([]);
  });

  test("ignores responses without stylesheets and full pages", () => {
    expect(extract_partial_stylesheets("<div>plain</div>", "http://x/")).toEqual([]);
    expect(
      extract_partial_stylesheets(
        "<html><head><style>.a{}</style></head><body><p>page</p></body></html>",
        "http://x/",
      ),
    ).toEqual([]);
  });

  test("keys dev styles by their vite id so the page's copy is recognised", () => {
    const [, sheet] = extract_partial_stylesheets(
      '<!DOCTYPE html><link rel="stylesheet" href="/x.css"><style data-vite-dev-id="/src/Button.astro?astro&type=style">.b{}</style><p>x</p>',
      "http://x/",
    );
    expect(sheet.key).toBe("dev:/src/Button.astro?astro&type=style");
  });
});

describe("missing_rules_css", () => {
  test("keeps only rules the page lacks, including inside @media", () => {
    const page = rule_keys([
      rule(".flex-block { display: flex; }"),
      media("@media (min-width: 40em)", [".flex-block { gap: 1px; }"]),
    ]);
    const partial = [
      rule(".pick-ships__rows[data-astro-cid-p1] { display: flex; }"),
      rule(".flex-block { display: flex; }"),
      media("@media (min-width: 40em)", [
        ".pick-ships__row[data-astro-cid-p1] { display: grid; }",
        ".flex-block { gap: 1px; }",
      ]),
    ];

    const css = missing_rules_css(partial, page);

    expect(css).toContain(".pick-ships__rows[data-astro-cid-p1] { display: flex; }");
    expect(css).toContain("@media (min-width: 40em) {");
    expect(css).toContain(".pick-ships__row[data-astro-cid-p1] { display: grid; }");
    expect(css).not.toContain(".flex-block");
  });

  test("returns nothing when the page already has every rule", () => {
    const rules = [rule(".a { color: red; }"), media("@media print", [".a { color: black; }"])];
    expect(missing_rules_css(rules, rule_keys(rules))).toBe("");
  });
});

describe("apply_partial_stylesheets", () => {
  test("adds each sheet once, however often the partial is swapped", async () => {
    const fetch_css = vi.fn(async () => ".picker[data-astro-cid-p1] { color: red; }");

    const first = apply_partial_stylesheets(document, PARTIAL, fetch_css);
    for (let i = 0; i < 5; i++) apply_partial_stylesheets(document, PARTIAL, fetch_css);

    expect(first).toHaveLength(2);
    expect(document.head.querySelectorAll(`[${PARTIAL_STYLE_ATTRIBUTE}]`)).toHaveLength(2);
    expect(fetch_css).toHaveBeenCalledTimes(1);

    await vi.waitFor(() =>
      expect(document.head.textContent).toContain(".picker[data-astro-cid-p1]"),
    );
  });

  test("skips a linked sheet the page already loads", () => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/_astro/picker.css";
    document.head.appendChild(link);
    const fetch_css = vi.fn(async () => "");

    const added = apply_partial_stylesheets(document, PARTIAL, fetch_css);

    expect(added.some((key) => key.startsWith("link:"))).toBe(false);
    expect(fetch_css).not.toHaveBeenCalled();
  });
});

describe("bind_partial_styles", () => {
  test("binds once and applies styles before htmx swaps", () => {
    const win = window as Window & { __minmatar_partial_styles_bound?: boolean };
    delete win.__minmatar_partial_styles_bound;
    const add = vi.spyOn(document, "addEventListener");

    bind_partial_styles(win);
    bind_partial_styles(win);

    expect(add.mock.calls.filter(([name]) => name === "htmx:beforeSwap")).toHaveLength(1);
    add.mockRestore();

    document.dispatchEvent(
      new CustomEvent("htmx:beforeSwap", {
        detail: {
          shouldSwap: true,
          xhr: { responseText: '<!DOCTYPE html><link rel="stylesheet" href="/x.css"><style>.only-in-partial{color:red}</style><p>x</p>' },
        },
      }),
    );
    document.dispatchEvent(
      new CustomEvent("htmx:beforeSwap", {
        detail: {
          shouldSwap: false,
          xhr: { responseText: '<!DOCTYPE html><link rel="stylesheet" href="/y.css"><style>.error-page{color:red}</style><p>x</p>' },
        },
      }),
    );

    const added = document.head.querySelectorAll(`[${PARTIAL_STYLE_ATTRIBUTE}]`);
    expect(Array.from(added, (el) => el.getAttribute(PARTIAL_STYLE_ATTRIBUTE))).toEqual([
      "link:http://localhost:3000/x.css",
      expect.stringMatching(/^style:/),
    ]);
    expect(added[1].textContent).toContain(".only-in-partial");
  });
});

test("both layouts install the partial styles hook", async () => {
  const { readFileSync } = await import("node:fs");
  const { dirname, join } = await import("node:path");
  const { fileURLToPath } = await import("node:url");
  const partials = join(dirname(fileURLToPath(import.meta.url)), "../../src/components/partials");

  for (const name of ["HeadScripts.astro", "GuestsHeadScripts.astro"]) {
    expect(readFileSync(join(partials, name), "utf8"), name).toContain("bind_partial_styles(window)");
  }
});
