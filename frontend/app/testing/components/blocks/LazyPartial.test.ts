import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import LazyPartial from "@components/blocks/LazyPartial.astro";

function attributes(html: string): Record<string, string> {
  const el = new DOMParser().parseFromString(html, "text/html").body.firstElementChild as Element;
  return Object.fromEntries(Array.from(el.attributes, (a) => [a.name, a.value]));
}

test("LazyPartial loads once on page load into itself", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(LazyPartial, {
    props: { url: "/partials/loyalty_offers_component", id: "loyalty-offers-slot" },
    slots: { default: "<p>Loading…</p>" },
  });
  const attrs = attributes(html);

  expect(attrs).toMatchObject({
    id: "loyalty-offers-slot",
    "hx-get": "/partials/loyalty_offers_component",
    "hx-trigger": "load",
    "hx-swap": "innerHTML",
    // Never inherit a surrounding <form>'s hx-target (DialogButton forms).
    "hx-target": "this",
    "hx-indicator": ".loader",
    "aria-busy": "true",
    "aria-live": "polite",
    "hx-on--after-request": "this.setAttribute('aria-busy', 'false')",
  });
  expect(html).toContain("<p>Loading…</p>");
});

test("LazyPartial reveal trigger, outer swap, no indicator and an after_request hook", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(LazyPartial, {
    props: {
      url: "/partials/order_coordinators_component?order_id=1",
      trigger: "reveal",
      swap: "outerHTML",
      indicator: false,
      after_request: "this.closest('.stack')?.classList.remove('is-loading')",
      class: "[ order-coordinators-lazy ]",
    },
  });
  const attrs = attributes(html);

  expect(attrs["hx-trigger"]).toBe("intersect once");
  expect(attrs["hx-swap"]).toBe("outerHTML");
  expect(attrs["hx-indicator"]).toBeUndefined();
  expect(attrs["hx-on--after-request"]).toBe(
    "this.setAttribute('aria-busy', 'false'); this.closest('.stack')?.classList.remove('is-loading')",
  );
  expect(attrs.class).toBe("[ order-coordinators-lazy ]");
});
