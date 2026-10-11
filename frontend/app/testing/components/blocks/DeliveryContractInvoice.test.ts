import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

test("DeliveryContractInvoice does not call update_tooltip on init", () => {
  const src = readFileSync(
    join(
      dirname(fileURLToPath(import.meta.url)),
      "../../../src/components/blocks/DeliveryContractInvoice.astro",
    ),
    "utf8",
  );

  expect(src).not.toContain('x-init="update_tooltip()"');
});
