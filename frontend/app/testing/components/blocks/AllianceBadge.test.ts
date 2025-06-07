import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";

import AllianceBadge from "@components/blocks/AllianceBadge.astro";

import { get_alliance_by_id } from "@helpers/api.eveonline/alliances";
import { get_alliance_logo } from "@helpers/eve_image_server";

vi.mock("@helpers/api.eveonline/alliances");
vi.mock("@helpers/eve_image_server");

test("AllianceBadge defaults", async () => {
  vi.mocked(get_alliance_by_id).mockImplementation(async (id) => {
    expect(id).toBe(42);

    return {
      name: "lolcat alliance is best alliance",
      creator_corporation_id: 1,
      creator_id: 1,
      date_founded: new Date(),
      executor_corporation_id: 1,
      faction_id: 1,
      ticker: "TICK",
    };
  });

  vi.mocked(get_alliance_logo).mockImplementation((id, size) => {
    expect(id).toBe(42);
    expect(size).toBe(32);

    return "test-alliance-image-src";
  });

  const container = await AstroContainer.create();
  const result = await container.renderToString(AllianceBadge, {
    props: {
      alliance: {
        id: 42,
      },
    },
  });

  // expect(result).toMatchSnapshot();
});
