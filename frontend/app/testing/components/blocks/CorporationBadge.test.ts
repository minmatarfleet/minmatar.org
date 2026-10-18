import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationBadge from "@components/blocks/CorporationBadge.astro";

import { get_corporation_by_id } from "@helpers/api.eveonline/corporations";
vi.mock("@helpers/api.eveonline/corporations");

test("CorporationBadge defaults", async () => {
  vi.mocked(get_corporation_by_id).mockResolvedValue({
    alliance_id: 43,
    ceo_id: 98,
    creator_id: 98,
    date_founded: new Date("2100-01-01"),
    description: "a great corp",
    faction_id: 1,
    home_station_id: 65,
    member_count: 91,
    name: "chicken attack",
    shares: 12,
    tax_rate: 1,
    ticker: "CHICK",
    url: "chicken.com",
    war_eligible: true,
  });
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationBadge, {
    props: {
      corporation: {
        id: 12,
        name: "chicken attack",
      },
    },
  });

  // expect(result).toMatchSnapshot();
});

const render_badge = async (
  size: "xs" | "sm" | "lg",
  show_modal: boolean,
  slot?: string,
) => {
  const container = await AstroContainer.create();
  return container.renderToString(CorporationBadge, {
    props: {
      corporation: { id: 98000001, name: "Lolcat Industries", size },
      show_modal,
    },
    slots: slot ? { default: slot } : {},
  });
};

test.each(["xs", "sm", "lg"] as const)(
  "CorporationBadge %s with show_modal is a single link around the name",
  async (size) => {
    const result = await render_badge(size, true);

    // A nested <a> makes the parser close the outer link before the name.
    expect(result.match(/<a[\s>]/g)).toHaveLength(1);
    const link = result.slice(result.indexOf("<a"), result.indexOf("</a>"));
    expect(link).toContain('href="/alliance/corporations/');
    expect(link).toContain("Lolcat Industries");
  },
);

test.each(["xs", "sm", "lg"] as const)(
  "CorporationBadge %s without show_modal renders no link",
  async (size) => {
    const result = await render_badge(size, false);
    expect(result).not.toMatch(/<a[\s>]/);
    expect(result).toContain("Lolcat Industries");
  },
);

test.each(["xs", "sm", "lg"] as const)(
  "CorporationBadge %s renders its slot",
  async (size) => {
    const result = await render_badge(size, true, "<small>Fleet commander</small>");
    expect(result).toContain("<small>Fleet commander</small>");
  },
);

test("CorporationBadge lg falls back to the description without a slot", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationBadge, {
    props: {
      corporation: { id: 1, name: "Corp", size: "lg", description: "3 years" },
    },
  });
  expect(result).toContain("<small>3 years</small>");
});
