import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import DiscordLoginNotice from "@components/blocks/DiscordLoginNotice.astro";
import { get_discord_oauth_login_action, get_discord_oauth_redirect_url, get_discord_oauth_start_url } from "@helpers/env";

test("discord oauth start url keeps redirect_url in the query", () => {
    const start = get_discord_oauth_start_url();
    const action = get_discord_oauth_login_action();
    const redirect = get_discord_oauth_redirect_url();

    expect(action.endsWith("/api/users/login")).toBe(true);
    expect(action).not.toContain("redirect_url");
    expect(redirect.endsWith("/auth/login")).toBe(true);
    expect(start.startsWith(`${action}?redirect_url=`)).toBe(true);
    expect(start).toContain(encodeURIComponent(redirect));
});

test("discord login notice submits without waiting for Alpine", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(DiscordLoginNotice);
    const action = result.match(/<form[^>]*\saction="([^"]*)"/)?.[1] ?? "";
    const redirect = result.match(/name="redirect_url" value="([^"]*)"/)?.[1] ?? "";
    const submit = result.match(/<button type="submit"[^>]*>/)?.[0] ?? "";

    expect(result).toContain('method="get"');
    expect(action).toContain("/api/users/login");
    expect(action).not.toContain("redirect_url");
    expect(action).not.toContain("?");
    expect(redirect).toContain("/auth/login");
    expect(result).toContain('id="discord-login-notice-leave-checkbox"');
    expect(result).toContain("required");
    expect(submit).toContain('type="submit"');
    expect(submit).not.toContain("disabled");
    expect(result).toContain("discord_login_notice_accepted");
    expect(result).not.toContain("accept_notice");
    expect(result).not.toContain("x-bind:disabled");
    expect(result).not.toContain("removeAttribute");
});
