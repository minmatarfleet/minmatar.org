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
| Create a tribe | `POST /api/tribes/` (`name`, optional `slug`, `description`) | Creates the tribe and an auth group named after it. `discord.signals.group_post_save` then makes the Discord role, or links an existing role with that name. The slug comes from the name when empty. |
| Create a group | `POST /api/tribes/{tribe_id}/groups` (`name`, `description`) | Creates the group, its auth group and Discord role. Its code is `{tribe slug}.{name}`. Not allowed in an archived tribe. |
| Rename | `PATCH /api/tribes/{tribe_id}` or `.../groups/{group_id}` (`name`) | Renames the auth group and the Discord role with it. The slug and the group code never change: reports and bindings key on them. |
| Archive, restore | the same `PATCH` (`is_active`) | Sets `is_active`, as the admin did. Memberships and roles are left alone. A group can only be restored in an active tribe. |
| List archived | `GET /api/tribes/?archived=true`, `GET /api/tribes/{tribe_id}/groups?archived=true` | Archived tribes or groups, to restore them. Managers only (403 otherwise). |
| Change a chief | `PUT /api/tribes/{tribe_id}/chief`, `.../groups/{group_id}/chief` | The chief swap (`tribes.helpers.chiefs.set_chief`); the API's `can_set_chief` flag follows the feature. |

A name already used by another auth group (and so a Discord role) is
refused, so a tribe never takes over an unrelated role. If Discord fails
while creating or renaming, nothing is saved and the API answers 502.
