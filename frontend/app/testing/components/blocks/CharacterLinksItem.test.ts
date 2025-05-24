import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CharacterLinksItem from "@components/blocks/CharacterLinksItem.astro";

import { get_user_permissions } from "@helpers/permissions";

vi.mock("@helpers/permissions");

test("CharacterLinksItem defaults", async () => {
  vi.mocked(get_user_permissions).mockImplementation(async (id) => {
    expect(id).toBe("mrCluckAndStuff");
    return ["cluck", "peck"];
  });

  const container = await AstroContainer.create();
  const result = await container.renderToString(CharacterLinksItem, {
    props: {
      character: {
        character_id: 45,
        character_name: "bagok",
        corporation: 7,
      },
      user: {
        username: "mrCluckAndStuff",
      },
    },
  });

  expect(result).toMatchSnapshot();
});
