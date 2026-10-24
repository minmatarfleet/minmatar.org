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
  // Disarms when the surrounding Dropdown closes, and works outside one.
  expect(result).toContain("typeof expanded === 'undefined' || expanded");
  expect(result).toContain('x-on:click.outside="confirming = false"');
  expect(result).toContain('x-on:keydown.escape="confirming = false"');
});

test("href item renders one link carrying the attributes", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: { href: "/fleets/upcoming/edit/7", "x-on:click": "close()" },
    slots: { default: "Edit fleet" },
  });

  expect(result).not.toContain("<button");
  expect(result).toMatch(/<a href="\/fleets\/upcoming\/edit\/7"[^>]*x-on:click="close\(\)"/);
  expect(result).toContain("Edit fleet");
});

test("submit item keeps its type for forms", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: { type: "submit" },
    slots: { default: "Refresh MOTD" },
  });

  expect(result.match(/type="/g)).toHaveLength(1);
  expect(result).toContain('type="submit"');
});

test("text-only item is a status line, not a control", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: { variant: "success", text_only: true },
    slots: { default: "Twitch connected" },
  });

  expect(result).not.toMatch(/<(button|a)[\s>]/);
  expect(result).toContain("action-menu-item--success");
  expect(result).toContain("action-menu-item--text");
});

test("tribe withdraw: htmx request sits on the confirm button only", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenuItem, {
    props: {
      variant: "danger",
      confirm_label: "Confirm",
      "hx-delete": "/partials/tribe_group_status_component?membership_id=3",
      "hx-target": "#tribe-group-status-1-2",
    },
    slots: { default: "Withdraw" },
  });

  const buttons = result.match(/<button[^>]*>/g) ?? [];
  expect(buttons).toHaveLength(2);
  expect(buttons[0]).not.toContain("hx-delete");
  expect(buttons[1]).toContain("hx-delete");
  expect(buttons[1]).toContain('hx-target="#tribe-group-status-1-2"');
  expect(buttons[0]).toContain("confirming = true");
});
