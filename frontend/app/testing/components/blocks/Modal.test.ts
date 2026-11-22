import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import { ModalXData, PersistentModalXData } from "@components/partials/AlpineScripts.astro";
import Modal from "@components/blocks/Modal.astro";

test("Modal clears its partial after the swap with an Alpine handler, not a global hx-on function", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Modal, {});

  expect(result).toContain("x-on:htmx:after-swap=\"if ($event.target === $el) { modal_partial = ''; modal_partial_params = '' }\"");
  expect(result).not.toContain("minmatar_modal_after_swap");
  expect(result).not.toMatch(/hx-on/);
});

test("Modal never re-initialises swapped content itself", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Modal, {});

  expect(result).not.toContain("initTree");
  expect(ModalXData).not.toContain("htmx.process");
  expect(PersistentModalXData).not.toContain("htmx.process");
});

test("persistent Modal has no backdrop action, the plain one has", async () => {
  const container = await AstroContainer.create();
  const plain = await container.renderToString(Modal, {});
  const persistent = await container.renderToString(Modal, { props: { persistent: true } });

  expect(plain).toMatch(/modal-backdrop[^>]*modal-action="cancel"/);
  expect(persistent).toContain("persistent-modal-backdrop");
  expect(persistent).not.toMatch(/persistent-modal-backdrop[^>]*persistent-modal-action/);
  expect(persistent).toContain('persistent-modal-action="cancel"');
});
