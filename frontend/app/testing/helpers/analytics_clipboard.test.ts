import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

// public/js scripts are plain globals loaded by FooterScripts; load them the same way.
const load = (file: string) => (0, eval)(readFileSync(resolve(__dirname, "../../public/js", file), "utf8"));

// Loaded at runtime from public/js/clipboard.js, so call it through the global object.
const copy = (element_id: string, alert_text?: string | null, source?: string) =>
    (globalThis as any).copyFitToClipboard(element_id, alert_text, source);

let write_text: ReturnType<typeof vi.fn>;

beforeEach(() => {
    load("analytics.js");
    load("clipboard.js");
    document.body.innerHTML = '<textarea id="fit">[Rifter, Rifter]</textarea>';
    write_text = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: write_text }, configurable: true });
});

afterEach(() => {
    delete (window as any).posthog;
});

test("copy works and nothing throws when PostHog is absent", () => {
    expect(() => window.capture_event?.("anything", { a: 1 })).not.toThrow();
    expect(() => copy("fit", null, "fitting")).not.toThrow();
    expect(write_text).toHaveBeenCalledWith("[Rifter, Rifter]");
});

test("a tagged fitting copy sends fitting_copied with only the source", () => {
    const capture = vi.fn();
    (window as any).posthog = { capture };
    copy("fit", null, "fitting");
    expect(write_text).toHaveBeenCalledWith("[Rifter, Rifter]");
    expect(capture).toHaveBeenCalledWith("fitting_copied", { source: "fitting" }, undefined);
});

test("an untagged copy sends nothing", () => {
    const capture = vi.fn();
    (window as any).posthog = { capture };
    copy("fit");
    expect(write_text).toHaveBeenCalled();
    expect(capture).not.toHaveBeenCalled();
});

test("a failing PostHog capture never breaks the copy", () => {
    (window as any).posthog = { capture: () => { throw new Error("blocked"); } };
    expect(() => copy("fit", null, "fitting")).not.toThrow();
    expect(write_text).toHaveBeenCalledWith("[Rifter, Rifter]");
});
