// Scratch harness (not committed): renders a component at HEAD and in the working tree, normalised, and diffs the HTML.
// RD_FILE=src/components/blocks/X.astro RD_PROPS=/path/props.json npm run test -- --run testing/scratch/render_diff.test.ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import { execSync } from "node:child_process";
import { copyFileSync, existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, basename, join, resolve } from "node:path";

const file = process.env.RD_FILE!;
const props = process.env.RD_PROPS ? JSON.parse(readFileSync(process.env.RD_PROPS, "utf8")) : {};
const url = process.env.RD_URL ?? "http://localhost:4321/";

const norm = (html: string) =>
  html
    .replace(/\s*data-astro-cid(?:-[a-z0-9]+)?(?:="true")?/g, "")
    .replace(/(<button[^>]*>)\s+/g, "$1")
    .replace(/\s+<\/button>/g, "</button>")
    .replace(/<(button|a|input|select|textarea)\b((?:\s+[^\s=>"]+(?:="[^"]*")?)*)\s*>/g, (_m, tag, rest) =>
      `<${tag} ${(rest.match(/[^\s=>"]+(?:="[^"]*")?/g) ?? []).sort().join(" ")}>`)
    .replace(/<style[\s\S]*?<\/style>/g, "")
    .replace(/\s+/g, " ")
    .replace(/> </g, ">\n<");

const KEEP = /^(name|value|type|checked|selected|disabled|required|readonly|multiple|min|max|step|pattern|maxlength|rows|id|for|form|formaction|hx-[\w:-]+|x-[\w:.-]+|@[\w:.-]+|:[\w:.-]+|aria-[\w-]+)(=|$)/;
const signatures = (html: string) =>
  [...html.matchAll(/<(button|input|select|textarea|option|a|label)\b((?:\s+[^\s=>"]+(?:="[^"]*")?)*)\s*>/g)]
    .filter((m) => m[1] !== "a" && m[1] !== "label" || /\s(hx-|x-on|@)/.test(m[2]))
    .map((m) => `${m[1]} ${(m[2].match(/[^\s=>"]+(?:="[^"]*")?/g) ?? []).filter((x) => KEEP.test(x)).sort().join(" ")}`);

test.skipIf(!file)("render diff", async () => {
  const abs = resolve(file);
  const before = join(dirname(abs), `${basename(abs, ".astro")}__before.astro`);
  const rel = execSync("git rev-parse --show-prefix", { cwd: dirname(abs) }).toString().trim() + basename(abs);
  writeFileSync(before, execSync(`git show HEAD:${rel}`, { cwd: dirname(abs), maxBuffer: 1 << 26 }));
  try {
    const container = await AstroContainer.create();
    const mod_after = (await import(/* @vite-ignore */ abs)).default;
    const mod_before = (await import(/* @vite-ignore */ before)).default;
    const opts = { props, request: new Request(url) };
    const a = norm(await container.renderToString(mod_before, opts));
    const b = norm(await container.renderToString(mod_after, opts));
    writeFileSync("/root/.local/share/minmatar-rust-alignment/w8/before.html", a);
    writeFileSync("/root/.local/share/minmatar-rust-alignment/w8/after.html", b);
    // RD_FIELDS=1: only the behaviour-bearing attributes of each control must match, not the markup around it.
    if (process.env.RD_FIELDS) {
      expect(signatures(b)).toEqual(signatures(a));
    } else {
      expect(b).toBe(a);
    }
  } finally {
    if (existsSync(before)) unlinkSync(before);
  }
});
