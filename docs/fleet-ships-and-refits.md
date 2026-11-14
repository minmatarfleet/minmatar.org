# Fleet ships, refits and in-game fittings

Upcoming fleets carry a ship list (the doctrine's fits plus any fleet-specific
catalog picks or pasted EFT), pilot volunteers per ship, FC-configured refits
and a private cyno system assignment per cyno volunteer.

## In-game fittings (ESI)

Refits and custom (pasted EFT) fits are saved as fittings under the fleet
commander's character through ESI so the MOTD can link them. This needs the
`esi-fittings.write_fittings.v1` scope, exposed as the `FleetCommander`
token type (`eveonline/scopes.py`). The UI prompts the FC to add it when a
character lacks it; the API rejects the create with a 400 until then.

**Deployment:** the EVE SSO application must be registered for
`esi-fittings.write_fittings.v1`, otherwise the "Add Fleet Commander token"
login fails with `invalid_scope`.

Saved fittings are named `MM#<fleet id> <label>` and are deleted when the
fleet completes, is cancelled, auto-closes after losing its boss, is deleted,
or when the FC removes the refit or fit. A failed delete is logged and retried
on the next close (`fleets/helpers/esi_fittings.py`).

## MOTD

`fleets/motd.py` renders fits and refits as in-game `fitting:` DNA links
(`fleets/helpers/eft_items.py`). ESI caps the MOTD at 4000 characters; when a
fleet overflows, the refit section is dropped first, then fit links fall back
to web links.

## Roles from ships

Fleet roles fill themselves from the ship a pilot volunteers or is flying in
fleet (`backend/fleets/helpers/fit_roles.py`, read off the fit's EFT):

- **Links**: online command bursts; the pilot picks which kinds they run.
- **Logi**: two or more remote reps or cap transfers, or one on a logi hull.
- **Cynos**: any cynosural field generator.
- **Interdiction**: an Interdiction Sphere Launcher, Warp Disruption Field
  Generator or Micro Jump Field Generator.
- **ECM**: any ECM jammer or ECM burst.
- **Neuts**: two or more energy neutralizers.

`GET /api/fleets/{id}/roles` (`backend/fleets/helpers/role_coverage.py`)
lists who fills each. Logi FC is the one role still signed up for. The
website counts "X of Y roles filled" from rows with a target: Logi FC, each
link kind, cynos (2), and on strategic fleets interdiction (2), neuts (2)
and ECM (1). The backend sends those last three as `wanted`
(`INTERDICTION_WANTED`, `NEUTS_WANTED`, `ECM_WANTED`), 0 on other fleets,
where the rows list who brings them without a target. A row shows only when
a composition fit fills the role or a pilot already brings it. The desktop
fleet window still lists only logi, links and cyno.

## Cyno systems

The system an FC assigns to a cyno volunteer is never written to the MOTD or
returned to other pilots; it is sent to the volunteer by Discord DM
(`fleets/helpers/cyno_notifications.py`).
