import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import { AlertDialogXData } from "@components/partials/AlpineScripts.astro";
import AlertDialog from "@components/blocks/AlertDialog.astro";

test("alert dialog defers reset when Open has an accept href", () => {
    expect(AlertDialogXData).toContain("window.__schedule_alert_dialog_reset");
    expect(AlertDialogXData).toContain("accept_href: this.alert_dialog_accept_href");
    expect(AlertDialogXData).toContain("setTimeout(finish, 0)");
});

test("AlertDialog installs the reset helper and Open is a new-tab link", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(AlertDialog, {});

    expect(result).toContain("x-bind:href=\"alert_dialog_accept_href\"");
    expect(result).toContain("alert-dialog-action=\"accept\"");
});
