import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AugaInfo from "@components/blocks/AugaInfo.astro";

test("AugaInfo defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(AugaInfo, {});

  // expect(result).toMatchSnapshot();
});
