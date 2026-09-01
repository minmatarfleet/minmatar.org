import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Dropdown from "@components/blocks/Dropdown.astro";

test("teleported dropdown panel processes htmx after Alpine mounts it", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Dropdown, {
    slots: {
      button: "Actions",
      default: '<button hx-patch="/partials/example" type="button">Confirm</button>',
    },
  });

  expect(result).toContain('x-teleport="body"');
  expect(result).toContain("htmx.process($el)");
  expect(result).toContain("$watch('expanded'");
  expect(result).toContain('hx-patch="/partials/example"');
});
