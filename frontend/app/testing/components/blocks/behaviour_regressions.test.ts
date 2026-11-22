import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import EntityPicker from "@components/blocks/manage/EntityPicker.astro";
import CharacterPicture from "@components/blocks/CharacterPicture.astro";
import StructureHowTo from "@components/blocks/structures/StructureHowTo.astro";
import DataTable from "@components/blocks/DataTable.astro";

// Behaviour parity with main, found by the base-vs-PR flow run.

test("EntityPicker keeps its visible field out of the form, so required is checked by the server (as on main)", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(EntityPicker, {
    props: { id: "p", kind: "system", name: "system_id", label: "System", required: true },
  });
  const visible = html.match(/<input[^>]*role="combobox"[^>]*>/)?.[0] ?? "";
  expect(visible).toMatch(/ form( |=""|>)/);
});

test("CharacterPicture nested in a button keeps the click but adds no interactive role", async () => {
  const container = await AstroContainer.create();
  const plain = await container.renderToString(CharacterPicture, { props: { character_id: 42, character_name: "x" } });
  const nested = await container.renderToString(CharacterPicture, { props: { character_id: 42, character_name: "x", nested: true } });
  expect(plain).toContain('role="button"');
  expect(nested).not.toContain('role="button"');
  expect(nested).not.toContain('tabindex="0"');
  expect(nested).toContain("show_character_modal()");
});

test("StructureHowTo renders no tab role for a single topic", async () => {
  const container = await AstroContainer.create();
  const one = await container.renderToString(StructureHowTo, { props: { topics: ["name"] } });
  const two = await container.renderToString(StructureHowTo, { props: { topics: ["name", "owner"] } });
  expect(one).not.toContain('role="tab"');
  expect(two).toContain('role="tab"');
});

test("DataTable without a caption is not a landmark region", async () => {
  const container = await AstroContainer.create();
  const bare = await container.renderToString(DataTable, { props: { columns: [{ key: "a", label: "A" }] } });
  const named = await container.renderToString(DataTable, { props: { columns: [{ key: "a", label: "A" }], caption: "Things" } });
  expect(bare).not.toContain('role="region"');
  expect(named).toContain('role="region"');
});
