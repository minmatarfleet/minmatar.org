import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationMembersBlock from "@components/blocks/CorporationMembersBlock.astro";

import BlockList from "@components/compositions/BlockList.astro";

import CorporationBadge from "@components/blocks/CorporationBadge.astro";
import CorporationMemberItem from "@components/blocks/CorporationMemberItem.astro";
import ComponentBlockHeader from "@components/blocks/ComponentBlockHeader.astro";

vi.mock("@components/compositions/BlockList.astro");
vi.mock("@components/blocks/CorporationBadge.astro");
vi.mock("@components/blocks/CorporationMemberItem.astro");
vi.mock("@components/blocks/ComponentBlockHeader.astro");

test("CorporationMembersBlock defaults", async () => {
  vi.mocked(BlockList).mockReturnValue("BlockList_component");
  vi.mocked(CorporationBadge).mockReturnValue("CorporationBadge_component");
  vi.mocked(CorporationMemberItem).mockReturnValue(
    "CorporationMemberItem_component"
  );
  vi.mocked(ComponentBlockHeader).mockReturnValue(
    "ComponentBlockHeader_component"
  );

  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationMembersBlock, {
    props: {
      corporation: {
        corporation_id: 2356,
        members: [
          {
            character_id: 12,
          },
        ],
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
