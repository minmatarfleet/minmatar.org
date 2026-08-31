import { expect, test } from "vitest";
import { tag_ids_from_form_data } from "@helpers/character_tags_form";

test("tag_ids_from_form_data reads checked role ids", () => {
  const form_data = new FormData();
  form_data.append("tag", "1");
  form_data.append("tag", "7");
  expect(tag_ids_from_form_data(form_data)).toEqual([1, 7]);
});

test("tag_ids_from_form_data ignores empty and invalid values", () => {
  const form_data = new FormData();
  form_data.append("tag", "2");
  form_data.append("tag", "");
  form_data.append("tag", "nope");
  expect(tag_ids_from_form_data(form_data)).toEqual([2]);
});

test("tag_ids_from_form_data is empty when no roles are selected", () => {
  expect(tag_ids_from_form_data(new FormData())).toEqual([]);
});
