import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, test, vi } from "vitest";
import {
  TOOLTIP_TARGET,
  bind_swap_init,
  bind_tooltip_delegate,
  init_swapped_alpine,
  type SwapInitWindow,
} from "@helpers/swap_init";

function fake_window(extra: Partial<SwapInitWindow> = {}): SwapInitWindow {
  return { document, ...extra } as SwapInitWindow;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("init_swapped_alpine", () => {
  test("initialises a connected swap target", () => {
    const initTree = vi.fn();
    const target = document.createElement("div");
    document.body.appendChild(target);

    expect(init_swapped_alpine(fake_window({ Alpine: { initTree } }), target)).toBe(true);
    expect(initTree).toHaveBeenCalledWith(target);
  });

  test("leaves a detached (outerHTML-replaced) target to Alpine's observer", () => {
    const initTree = vi.fn();
    const detached = document.createElement("div");

    expect(init_swapped_alpine(fake_window({ Alpine: { initTree } }), detached)).toBe(false);
    expect(initTree).not.toHaveBeenCalled();
  });

  test("does nothing before Alpine has loaded", () => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    expect(init_swapped_alpine(fake_window(), target)).toBe(false);
  });
});

describe("bind_tooltip_delegate", () => {
  test("delegates once from <html> with the shared options and skips empty content", () => {
    const delegate = vi.fn();
    const win = fake_window({ tippy: { delegate }, tippy_options: { arrow: true } });

    expect(bind_tooltip_delegate(win)).toBe(true);
    expect(bind_tooltip_delegate(win)).toBe(true);

    expect(delegate).toHaveBeenCalledTimes(1);
    expect(delegate).toHaveBeenCalledWith(document.documentElement, {
      arrow: true,
      target: TOOLTIP_TARGET,
    });

    document.body.innerHTML =
      '<span id="a" data-tippy-content="Why"></span><span id="b" data-tippy-content=""></span>';
    expect(
      Array.from(document.querySelectorAll(TOOLTIP_TARGET), (el) => el.id),
    ).toEqual(["a"]);
  });

  test("waits for tippy to load", () => {
    expect(bind_tooltip_delegate(fake_window())).toBe(false);
  });
});

describe("bind_swap_init", () => {
  test("binds one afterSwap listener per window and never calls htmx.process", () => {
    const initTree = vi.fn();
    const process = vi.fn();
    const win = fake_window({
      Alpine: { initTree },
      tippy: { delegate: vi.fn() },
    }) as SwapInitWindow & { htmx: { process: typeof process } };
    win.htmx = { process };

    bind_swap_init(win);
    bind_swap_init(win);

    const slot = document.createElement("div");
    document.body.appendChild(slot);
    document.dispatchEvent(new CustomEvent("htmx:afterSwap", { detail: { target: slot } }));

    expect(initTree).toHaveBeenCalledTimes(1);
    expect(process).not.toHaveBeenCalled();
  });
});

// The per-page re-init scripts and the init_tooltips prop this replaced must
// not creep back in.
describe("one swap re-initialiser", () => {
  const src = join(dirname(fileURLToPath(import.meta.url)), "../../src");

  function astro_files(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return astro_files(path);
      return name.endsWith(".astro") ? [path] : [];
    });
  }

  const files = astro_files(src).map((path) => ({
    path: path.slice(src.length + 1),
    text: readFileSync(path, "utf8"),
  }));

  test("no component takes an init_tooltips prop", () => {
    expect(files.filter((f) => /\binit_tooltips?\b/.test(f.text)).map((f) => f.path)).toEqual([]);
  });

  test("no inline hx-on re-init and no minmatar_after_*_swap hooks", () => {
    expect(
      files
        .filter((f) => /hx-on="htmx:afterSwap|minmatar_after_(outer|inner)_html_swap/.test(f.text))
        .map((f) => f.path),
    ).toEqual([]);
  });

  test("htmx:afterSwap listeners stay limited to feature logic that is not re-initialisation", () => {
    const listeners = files
      .filter((f) => f.text.includes("'htmx:afterSwap'"))
      .map((f) => f.path)
      .sort();

    expect(listeners).toEqual([
      "components/blocks/industry/guide-order-summary/OpenOrdersProfitSummary.astro",
      "pages/market/fitting_orders/[order_id].astro",
    ]);
  });
});
