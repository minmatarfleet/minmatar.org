import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ClipboardButton from "@components/blocks/ClipboardButton.astro";

const click_call = (html: string) => html.match(/copyFitToClipboard\([^)]*\)/)?.[0];

test("ClipboardButton without a source keeps its original copy call", async () => {
  const container = await AstroContainer.create();
  const plain = await container.renderToString(ClipboardButton, { props: { id: "fit" }, slots: { default: "eft" } });
  const prefixed = await container.renderToString(ClipboardButton, { props: { id: 56, alert_prefix: "what_the_cluck_" }, slots: { default: "eft" } });

  expect(click_call(plain)).toBe("copyFitToClipboard('fit')");
  expect(click_call(prefixed)).toBe("copyFitToClipboard('56', 'what_the_cluck_')");
});

test("ClipboardButton passes its source to the copy call", async () => {
  const container = await AstroContainer.create();
  const tagged = await container.renderToString(ClipboardButton, { props: { id: "fit", source: "fitting" }, slots: { default: "eft" } });
  const both = await container.renderToString(ClipboardButton, { props: { id: "fit", alert_prefix: "p", source: "fitting" }, slots: { default: "eft" } });

  expect(click_call(tagged)).toBe("copyFitToClipboard('fit', null, 'fitting')");
  expect(click_call(both)).toBe("copyFitToClipboard('fit', 'p', 'fitting')");
});
