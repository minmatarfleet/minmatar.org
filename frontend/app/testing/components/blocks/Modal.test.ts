import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Modal from "@components/blocks/Modal.astro";

test("Modal afterSwap handler is a named function, not inline hx-on JS", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Modal, {});

  expect(result).toContain('hx-on--after-swap="window.minmatar_modal_after_swap.call(this, event)"');
  expect(result).toContain("window.minmatar_modal_after_swap = function (event)");
  expect(result).not.toMatch(/hx-on=["']htmx:afterSwap:/);
  expect(result).not.toMatch(/hx-on--after-swap=["'][^"']*\/\//);
});
