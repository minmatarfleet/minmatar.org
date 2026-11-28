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

  expect(result).toContain('x-bind:disabled="error || !acknowledged"');
  expect(result).toContain('x-data="{ acknowledged: true }"');
  expect(result).toContain("x-on:submit=\"if (error || (typeof acknowledged !== 'undefined' && !acknowledged)) { $event.preventDefault() }\"");
  expect(result).not.toContain("override_requirements");
  expect(result).not.toContain("close_dialog(); $nextTick");
  expect(result).toContain('x-on:click="close_dialog()"');
  expect(result).toContain('x-bind:required="!roles.length"');
  expect(result).toContain("required");
});

test("ButtonCorpApply asks a blocked pilot to confirm before applying anyway", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ButtonCorpApply, {
    props: {
      corporation: {
        application_updated: new Date(),
        corporation_id: 8324,
        requirements_blocked: true,
        requirements_unmet: ["Fly our Cruisers doctrine"],
      },
    },
  });

  expect(result).toContain('x-data="{ acknowledged: false }"');
  expect(result).toMatch(/<li[^>]*>Fly our Cruisers doctrine<\/li>/);
  expect(result).toContain("want to apply anyway");
  expect(result).toMatch(/name="override_requirements" value="1" x-bind:disabled="!acknowledged"/);
  expect(result).toContain("Apply anyway");
});
