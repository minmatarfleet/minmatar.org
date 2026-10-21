import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AccountReferrals from "@components/blocks/AccountReferrals.astro";

const links = [
  { name: "Bookmarks", slug: "wiki_bookmarks", target: "https://example.com/bookmarks", link: "/external/wiki_bookmarks?ref=7", decription: "Guide" },
  { name: "Faction Warfare Complexes", slug: "wiki_fw_plexing", target: "https://example.com/plexing", link: "/external/wiki_fw_plexing?ref=7", decription: "Guide" },
];

test("AccountReferrals joins clicks onto guides, most clicked first, and lists other pages", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AccountReferrals, {
    props: {
      links,
      ref_code: "?ref=7",
      stats: [
        { name: "wiki_fw_plexing", title: "Faction Warfare Complexes", count: 9 },
        { name: "fleets", title: "Fleets", count: 2, target: "/fleets/" },
      ],
    },
  });

  expect(result).toContain("?ref=7");
  expect(result.indexOf("Faction Warfare Complexes")).toBeLessThan(result.indexOf("Bookmarks"));
  expect(result).toContain("Fleets");
  // Total is every click, guides and other pages.
  expect(result).toMatch(/account-referrals__total-number[^>]*>11</);
});
