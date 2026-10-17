import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import CharacterLinksItem from "@components/blocks/CharacterLinksItem.astro";
import CharacterLinks from "@components/blocks/CharacterLinks.astro";
import { ANONYMOUS_GATES, type GateContext } from "@helpers/gates";

const character = {
  character_id: 45,
  character_name: "bagok",
  corporation: 7,
};

function gates(overrides: Partial<GateContext>): GateContext {
  return { ...ANONYMOUS_GATES, user_id: 1, reported: new Set(), ...overrides };
}

test("CharacterLinksItem hides staff links without a signed-in viewer", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterLinksItem, {
    props: {
      character,
      user: { username: "mrCluckAndStuff" },
    },
  });

  expect(result).not.toContain("/character/skillsets");
  expect(result).not.toContain("/character/assets");
});

test("CharacterLinks shows staff links to holders of the legacy permission", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterLinks, {
    props: {
      character_id: 45,
      user: { username: "staff", is_superuser: false },
      gates: gates({ legacy_permissions: ["eveonline.view_evecharacter"] }),
    },
  });

  expect(result).toContain("/character/skillsets");
  expect(result).toContain("/character/assets");
});

test("CharacterLinks follows the feature in features mode", async () => {
  const container = await AstroContainer.create();
  const without_feature = await container.renderToString(CharacterLinks, {
    props: {
      character_id: 45,
      user: { username: "staff", is_superuser: false },
      gates: gates({
        gate_source: "features",
        legacy_permissions: ["eveonline.view_evecharacter"],
      }),
    },
  });
  const with_feature = await container.renderToString(CharacterLinks, {
    props: {
      character_id: 45,
      user: { username: "staff", is_superuser: false },
      gates: gates({ gate_source: "features", features: ["characters.view_staff"] }),
    },
  });

  expect(without_feature).not.toContain("/character/skillsets");
  expect(with_feature).toContain("/character/skillsets");
});
