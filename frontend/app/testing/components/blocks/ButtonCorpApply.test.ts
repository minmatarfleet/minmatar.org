import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ButtonCorpApply from "@components/blocks/ButtonCorpApply.astro";

test("ButtonCorpApply defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonCorpApply, {
    props: {
      corporation: {
        application_updated: new Date(),
        corporation_id: 8324,
      },
    },
  });

  expect(result).toContain('x-bind:disabled="error"');
  expect(result).toContain('x-on:submit="if (error) { $event.preventDefault() }"');
  expect(result).not.toContain("close_dialog(); $nextTick");
  expect(result).toContain('x-on:click="close_dialog()"');
  expect(result).toContain('x-bind:required="!roles.length"');
  expect(result).toContain("required");
});
