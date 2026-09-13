import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

test("FleetDetails null-guards preping-button removal", () => {
  const src = readFileSync(
    join(
      dirname(fileURLToPath(import.meta.url)),
      "../../../src/components/blocks/FleetDetails.astro",
    ),
    "utf8",
  );

  expect(src).toContain(
    "document.getElementById('preping-button')?.remove()",
  );
});
