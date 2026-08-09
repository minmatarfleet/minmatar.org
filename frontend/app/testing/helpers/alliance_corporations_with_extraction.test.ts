import { beforeEach, expect, test, vi } from "vitest";

import {
  append_extraction_corporation,
  get_alliance_corporations_with_extraction,
  MINMATAR_EXTRACTION_COMPANY_ID,
} from "@helpers/fetching/corporations";
import {
  get_all_corporations,
  get_corporation_info,
} from "@helpers/api.minmatar.org/corporations";

vi.mock("@helpers/api.minmatar.org/corporations");
vi.mock("@helpers/api.minmatar.org/applications", () => ({
  get_corporation_applications: vi.fn(),
  get_corporation_applications_by_id: vi.fn(),
}));
vi.mock("@helpers/fetching/characters", () => ({
  get_user_character: vi.fn(),
}));

const alliance_corp = {
  corporation_id: 98726134,
  corporation_name: "Rattini Tribe",
  alliance_id: 99011978,
  alliance_name: "Minmatar Fleet Alliance",
  type: "alliance" as const,
  introduction: "",
  biography: "",
  executor_notes: "",
  timezones: [],
  requirements: [],
  members: [],
  active: true,
  trial: false,
};

const extraction_corp = {
  corporation_id: MINMATAR_EXTRACTION_COMPANY_ID,
  corporation_name: "Minmatar Extraction Company",
  alliance_id: 99012009,
  alliance_name: "Minmatar Fleet Associates",
  type: "associate" as const,
  introduction: "",
  biography: "",
  executor_notes: "",
  timezones: [],
  requirements: [],
  members: [],
  active: true,
  trial: false,
};

beforeEach(() => {
  vi.clearAllMocks();
});

test("get_alliance_corporations_with_extraction appends M-EXC", async () => {
  vi.mocked(get_all_corporations).mockResolvedValue([{ ...alliance_corp }]);
  vi.mocked(get_corporation_info).mockResolvedValue({ ...extraction_corp });

  const corporations = await get_alliance_corporations_with_extraction();

  expect(get_all_corporations).toHaveBeenCalledWith("alliance");
  expect(get_corporation_info).toHaveBeenCalledWith(
    MINMATAR_EXTRACTION_COMPANY_ID,
  );
  expect(corporations.map((c) => c.corporation_id)).toEqual([
    alliance_corp.corporation_id,
    MINMATAR_EXTRACTION_COMPANY_ID,
  ]);
});

test("append_extraction_corporation skips when M-EXC already present", async () => {
  const corporations = [{ ...extraction_corp }];

  await append_extraction_corporation(corporations);

  expect(get_corporation_info).not.toHaveBeenCalled();
  expect(corporations).toHaveLength(1);
});
