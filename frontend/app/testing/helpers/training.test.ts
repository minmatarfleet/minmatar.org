import { describe, expect, test } from "vitest";
import {
  short_skill_points,
  skill_level,
  time_label,
  training_time,
  training_url,
} from "@helpers/training";

describe("training_time", () => {
  test("rounds to one number a pilot reads at a glance", () => {
    expect(training_time(0.02)).toEqual({ key: "training.under_hour", value: "" });
    expect(training_time(4 / 24)).toEqual({ key: "training.hours", value: "4" });
    expect(training_time(1.02)).toEqual({ key: "training.day", value: "1" });
    expect(training_time(2.14)).toEqual({ key: "training.days", value: "2.1" });
    expect(training_time(20.84)).toEqual({ key: "training.days", value: "21" });
  });

  test("time_label fills the template", () => {
    const t = (key: string) => ({ "training.days": "{value} days" })[key] ?? key;
    expect(time_label(t, 2.14)).toBe("2.1 days");
  });
});

test("short_skill_points", () => {
  expect(short_skill_points(58_400_000)).toBe("58M");
  expect(short_skill_points(820_000)).toBe("820k");
  expect(short_skill_points(12)).toBe("12");
});

test("skill_level uses EVE's roman numerals", () => {
  expect(skill_level(4)).toBe("IV");
});

test("training_url drops empty params", () => {
  expect(training_url("/partials/x/", { character_id: 5, fitting_id: undefined, mode: "" })).toBe(
    "/partials/x/?character_id=5",
  );
  expect(training_url("/partials/x/", {})).toBe("/partials/x/");
});
