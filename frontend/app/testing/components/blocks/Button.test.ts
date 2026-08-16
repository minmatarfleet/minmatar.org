import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import Button from "@components/blocks/Button.astro";

test("Button defaults", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Button, {});

  expect(result).toContain("[ button ]");
});

test("external Button looks up show_alert_dialog on body and passes accept_href", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Button, {
    props: {
      href: "https://discord.com/invite/3hZfahmkFx",
      external: true,
      size: "sm",
    },
    slots: {
      default: "Fleet Discord",
    },
  });

  expect(result).toContain("Alpine.$data(document.body)");
  expect(result).toContain("accept_href: 'https://discord.com/invite/3hZfahmkFx'");
  expect(result).toContain("root_data.show_alert_dialog");
  expect(result).not.toMatch(/[^.]show_alert_dialog\(\{/);
});

test("internal Button with href does not isolate an empty Alpine scope", async () => {
  const container = await AstroContainer.create();
  const result = await container.renderToString(Button, {
    props: {
      href: "/account/referrals/",
      size: "sm",
    },
    slots: {
      default: "Referral links",
    },
  });

  expect(result).toContain('href="/account/referrals/"');
  expect(result).not.toContain("x-data=");
  expect(result).not.toContain("x-on:click.prevent");
});
