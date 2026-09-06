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

## Cyno systems

The system an FC assigns to a cyno volunteer is never written to the MOTD or
returned to other pilots; it is sent to the volunteer by Discord DM
(`fleets/helpers/cyno_notifications.py`).
