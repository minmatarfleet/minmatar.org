import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AllianceList from "@components/blocks/AllianceList.astro";

test("AllianceList defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AllianceList, {});

  expect(result).toMatchSnapshot();
});
