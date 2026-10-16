import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import AddPilotDialog from "../../../src/pages/partials/add_pilot_dialog.astro";

const render = async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(AddPilotDialog, {
        request: new Request("http://localhost/partials/add_pilot_dialog?is_main=false"),
    });
    return html.replaceAll("&#34;", '"');
};

test("add character dialog requires Basic and Faction Warfare and defaults the rest", async () => {
    const html = await render();

    expect(html).toContain("esi-characters.read_notifications.v1");
    expect(html).toContain("26 scopes will be requested");
    expect(html).toContain("Role-specific, off by default");
    expect(html).toContain('"Industry":true');
    expect(html).toContain('"Director":false');
});

