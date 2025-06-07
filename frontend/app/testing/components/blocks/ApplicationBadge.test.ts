import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import ApplicationBadge from "@components/blocks/ApplicationBadge.astro";

test("ApplicationBadge defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(ApplicationBadge, {
    props: {
      character: {
        character_id: 42,
        character_name: "Anni Todako",
        corporation: 1337,
      },
      corporation: {
        id: 1337,
        name: "chicken farmers",
      },
      type: {},
    },
  });

  // expect(result).toMatchSnapshot();
});
