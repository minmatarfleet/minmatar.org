import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CorporationPicture from "@components/blocks/CorporationPicture.astro";

test("CorporationPicture defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CorporationPicture, {
    props: {
      corporation_id: 65,
      corporation_name: "death chick",
    },
  });

  expect(result).toContain("death chick");
});

test("CorporationPicture is a real link, and a span role=link when nested", async () => {
  const container = await AstroContainer.create();
  const props = { corporation_id: 65, corporation_name: "death chick" };

  const alone = await container.renderToString(CorporationPicture, { props });
  expect(alone).toMatch(/<a\b[^>]*href="[^"]*\/65\/"/);

  // Regression: an <a> inside an <a>/<button> makes the parser close the outer
  // element and ejects the markup from its Alpine x-data scope.
  const nested = await container.renderToString(CorporationPicture, { props: { ...props, nested: true } });
  expect(nested).not.toMatch(/<a\b/);
  expect(nested).not.toMatch(/<button\b/);
  expect(nested).toContain('role="link"');
  expect(nested).toContain('tabindex="0"');
  expect(nested).toContain("window.location.assign");
});
