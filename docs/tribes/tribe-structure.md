# Creating and archiving tribes and groups

Tribes and tribe groups are created, renamed and archived on the site, and
their chiefs changed, without opening `/admin/` (#3002). The Django admin
stays as break-glass for superusers.

## Who

Feature `tribes.structure.manage` (`auth_group` scope), wired to the
**People Team** auth group by default. Superusers always have it, and so
does anyone holding the admin's `tribes.change_tribe` permission. Leadership
can move it to another group in the pilot features admin without a code
change. `tribes.helpers.structure.can_manage_structure` is the one check.

## What happens

`backend/tribes/helpers/structure.py` does the work; each change is one
transaction and writes an audit entry.

| Change | API | Effect |
|---|---|---|
| Create a tribe | `POST /api/tribes/` (`name`, optional `slug`, `description`) | Creates the tribe and an auth group named after it. `discord.signals.group_post_save` then makes its Discord role. The slug comes from the name when empty. |
| Create a group | `POST /api/tribes/{tribe_id}/groups` (`name`, `description`) | Creates the group, its auth group and Discord role. Its code is `{tribe slug}.{name}`. Not allowed in an archived tribe. |
| Rename | `PATCH /api/tribes/{tribe_id}` or `.../groups/{group_id}` (`name`) | Renames the auth group and the Discord role with it. The slug and the group code never change: reports and bindings key on them. |
| Archive, restore | the same `PATCH` (`is_active`) | Sets `is_active`, as the admin did. Memberships and roles are left alone. A group can only be restored in an active tribe. |
| List archived | `GET /api/tribes/?archived=true`, `GET /api/tribes/{tribe_id}/groups?archived=true` | Archived tribes or groups, to restore them. Managers only (403 otherwise). |
| Change a chief | `PUT /api/tribes/{tribe_id}/chief`, `.../groups/{group_id}/chief` | The chief swap (`tribes.helpers.chiefs.set_chief`); the API's `can_set_chief` flag follows the feature. |

A create or rename is refused (400, the same answer as a taken name) when
the name, ignoring case, is already used by another auth group, by a stored
`DiscordRole`, or by any role on the Discord server, including hand-made
roles with no auth group behind them. The Discord signal links roles by
name, so without this a new group could pick up an unrelated role (a
leadership or FC role) and hand it to everyone added to it. A rename may
keep its own role's name with a different case.

Auth group names are global, so the names of tribes and groups are unique
across all tribes: two tribes can't both have a "Logistics" group. Name
the second one after its tribe ("Capitals Logistics").

Discord changes can't be rolled back, so the Discord call is the last step
of each transaction, after every database write and the audit entry. If
Discord fails, nothing is saved and the API answers 502. If the database
commit itself fails after Discord succeeded, the role is left created or
renamed on Discord; fix it in the admin.

## On the site

The `tribes.structure.manage` gate (`frontend/app/src/json/feature_gates.json`)
shows the controls. Each opens a dialog (`TribeStructureButton`) that posts to
`/partials/tribe_structure_component`, which sends the pilot to the changed
page, or shows the API's reason inside the dialog.

- `/alliance/tribes/`: **New tribe**, and links to the archived tribes.
- A tribe page: **Rename**, **New group** and **Archive** (or **Restore** on an
  archived tribe, tagged Archived), plus links to its archived groups.
- A group page: **Rename** and **Archive** (or **Restore**).
- Chiefs: click the chief's portrait, as before (`TribeChiefSwap`).
