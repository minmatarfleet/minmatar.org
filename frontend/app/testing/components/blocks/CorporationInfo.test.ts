import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationInfo from "@components/blocks/CorporationInfo.astro";

import { get_corporation_info } from "@helpers/api.minmatar.org/corporations";
import AllianceBadge from "@components/blocks/AllianceBadge.astro";
vi.mock("@helpers/api.minmatar.org/corporations");
vi.mock("@components/blocks/AllianceBadge.astro");

test("CorporationInfo defaults", async () => {
  vi.mocked(get_corporation_info).mockResolvedValue({
    corporation_id: 454,
    corporation_name: "chicken attack",
    alliance_id: 34523,
    active: true,
    alliance_name: "coop",
    faction_id: 1,
    faction_name: "minmatar",
    requirements: ["chicken"],
    biography: "",
    introduction: "",
    timezones: [],
    type: "alliance",
  });
  vi.mocked(AllianceBadge).mockReturnValue("AllianceBadge_component");

  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationInfo, {
    props: {
      corporation: {
        corporation_id: 2345,
      },
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
