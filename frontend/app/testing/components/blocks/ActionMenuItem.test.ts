import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ActionMenuItem from "@components/blocks/ActionMenuItem.astro";

test("plain item puts the action on the one button", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: { variant: "primary", "hx-post": "/partials/x" },
    slots: { default: "Complete" },
  });

  expect(result.match(/<button/g)).toHaveLength(1);
  expect(result).toContain('hx-post="/partials/x"');
  expect(result).toContain("action-menu-item--primary");
  expect(result).toContain("Complete");
});

test("confirm item only runs the action from the armed button", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: {
      variant: "danger",
      confirm_label: "Cancel this order?",
      "x-on:click": "set_status(7, 'cancelled'); close()",
    },
    slots: { default: "Cancel order" },
  });

  const buttons = result.match(/<button[^>]*>/g) ?? [];
  expect(buttons).toHaveLength(2);
  expect(buttons[0]).toContain('x-on:click.stop="confirming = true;');
  expect(buttons[1]).toContain('x-ref="confirm"');
  expect(buttons[0]).not.toContain("set_status");
  expect(buttons[1]).toContain("set_status(7, 'cancelled'); close()");
  expect(buttons[1]).toContain("is-confirm");
  expect(result).toContain("Cancel this order?");
  // Re-arms when the surrounding Dropdown closes.
  expect(result).toContain('x-effect="expanded || (confirming = false)"');
});
