import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import PageActions from "@components/page/PageActions.astro";

test("PageActions renders slot content in the live DOM, not Alpine templates", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(PageActions, {
    slots: {
      default: '<input type="text" placeholder="search" data-test="page-actions-search" />',
    },
  });

  expect(result).toContain('data-test="page-actions-search"');
  expect(result).toContain('placeholder="search"');
  expect(result).not.toMatch(/<template[^>]*x-if/);
  expect(result).not.toMatch(/x-teleport=["']#mobile-actions["']/);
  expect(result).not.toContain("viewport_width");
});

test("PageActions moves the live node after Alpine init instead of gating on viewport", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(PageActions, {
    slots: {
      default: '<input type="text" placeholder="search" />',
    },
  });

  expect(result).toContain("place_actions");
  expect(result).toContain('$nextTick(() => place_actions())');
  expect(result).toContain('x-ref="actions"');
  expect(result).toContain("appendChild");
  expect(result).toContain("page-actions-slot");
});
