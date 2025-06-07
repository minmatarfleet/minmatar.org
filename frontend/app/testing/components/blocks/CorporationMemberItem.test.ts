import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationMemberItem from "@components/blocks/CorporationMemberItem.astro";

test("CorporationMemberItem defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationMemberItem, {
    props: {
      member: {
        character_id: 2345,
        character_name: "deathchick",
        exempt: true,
        main_character: {
          character_name: "cluckers",
        },
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  // expect(result).toMatchSnapshot();
});
