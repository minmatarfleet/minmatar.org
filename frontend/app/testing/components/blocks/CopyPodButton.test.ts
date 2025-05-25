import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test, vi } from "vitest";
import CopyPodButton from "@components/blocks/CopyPodButton.astro";

test("CopyPodButton defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(CopyPodButton, {
    props: {
      pod: [
        {
          name: "super duper omega crystal alpha",
          amount: 6,
        },
      ],
    },
    slots: {
      default: "slotted chick",
    },
  });

  expect(result).toMatchSnapshot();
});
