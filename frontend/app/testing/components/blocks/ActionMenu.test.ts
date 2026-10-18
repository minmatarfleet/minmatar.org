import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ActionMenu from "@components/blocks/ActionMenu.astro";

test("passes the button trigger props through to Dropdown", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenu, {
    props: { variant: "button", color: "fleet-red", size: "lg", hover: "fill" },
    slots: { default: "<button>Edit</button>" },
  });

  expect(result).toContain("button-dropdown");
  expect(result).toContain("action-menu--fill");
  expect(result).toContain("Actions");
  expect(result).toContain('aria-label="Actions"');
});

test("tint hover is the default", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ActionMenu, {
    props: { label: "Manage" },
    slots: { default: "<button>Edit</button>" },
  });

  expect(result).not.toContain("action-menu--fill");
  expect(result).toContain('aria-label="Manage"');
});
