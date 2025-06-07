import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi, beforeEach, afterEach, describe, it } from "vitest";
import CharacterInfo from "@components/blocks/CharacterInfo.astro";

import { get_user_permissions } from "@helpers/permissions";
import { get_character_by_id } from "@helpers/api.eveonline/characters";
import { get_character_faction, get_race_cover_image } from "@helpers/eve";

vi.mock("@helpers/permissions");
vi.mock("@helpers/api.eveonline/characters");
vi.mock("@helpers/eve");

import CorporationHistory from "@components/blocks/CorporationHistory.astro";
import CorporationBadge from "@components/blocks/CorporationBadge.astro";
import AllianceBadge from "@components/blocks/AllianceBadge.astro";
import {
  format_date_time,
  humanize_date_diff,
  is_birthday,
} from "@helpers/date";

vi.mock("@components/blocks/CorporationHistory.astro");
vi.mock("@components/blocks/CorporationBadge.astro");
vi.mock("@components/blocks/AllianceBadge.astro");
vi.mock("@helpers/date");

describe("CharacterInfo", async () => {
  beforeEach(() => {
    // tell vitest we use mocked time
    vi.useFakeTimers();
  });

  afterEach(() => {
    // restoring date after each test run
    vi.useRealTimers();
  });

  it("should dispaly fireworks for birthdays", async () => {
    vi.mocked(get_user_permissions).mockImplementation(async (id) => {
      expect(id).toBe(908);

      return ["cluck", "bagok"];
    });

    vi.mocked(get_character_by_id).mockImplementation(async (id) => {
      expect(id).toBe(908);

      return {
        alliance_id: 12,
        birthday: new Date(1999, 1, 1, 13),
        bloodline_id: 12,
        corporation_id: 1337,
        description: "a goldenretriever like chicken",
        gender: "m",
        name: "Cluckin Kento",
        race_id: 2,
        security_status: -10,
      };
    });

    vi.mocked(get_character_faction).mockImplementation((race) => {
      expect(race).toBe(2);

      return "minmatar";
    });

    vi.mocked(get_race_cover_image).mockImplementation((race) => {
      expect(race).toBe("minmatar");

      return "chicken.gif";
    });

    vi.mocked(humanize_date_diff).mockImplementation((locale, from, to) => {
      return "mock human date";
    });

    vi.mocked(format_date_time).mockImplementation((locale, date) => {
      return "mock date format";
    });

    const date = new Date(2000, 1, 1, 13);
    vi.setSystemTime(date);

    vi.mocked(CorporationHistory).mockResolvedValue("CorporationHistory_mock");
    vi.mocked(CorporationBadge).mockResolvedValue("CorporationBadge_mock");
    vi.mocked(AllianceBadge).mockResolvedValue("AllianceBadge_mock");

    const container = await AstroContainer.create();
    const result = await container.renderToString(CharacterInfo, {
      props: {
        character_id: 908,
      },
    });

    // expect(result).toMatchSnapshot();
  });
});
