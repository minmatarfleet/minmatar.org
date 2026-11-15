# Signing up from a fleet invite

How a pilot answers a fleet invite DM, and why it works the way it does.
The changes came from the November 2026 fleet invite survey (116 of 390
invited pilots answered).

## What the pilot sees

The invite DM has three bot buttons:

| Button | What it does |
|---|---|
| **I'm available** | The bot replies, visible only to that pilot, with an **Open the picker** link. The link opens the sign-up page with no login. |
| **I'm not available** | Saves "not available" for this fleet only. Future invites still come. |
| **Stop fleet invites** | Standard fleets only: turns invite DMs off (Account › Notifications turns them back on). |

The DM says an answer is expected ("Tap I'm available or I'm not available
so the FC can plan. Either answer is fine."), that being late is fine, and
that saying no only skips this fleet. It no longer lists the pilot's
character names: anyone who saw a screenshot could read them.

The sign-up page (`/fleets/rsvp/<token>/` on the website):

- The fleet: FC, type, title, EVE time first, then the pilot's local time
  with the weekday, a countdown, form-up and doctrine.
- **How sure are you of making it on time?** High, Medium (might be 10-15
  minutes late) or Low (might not make it).
- **Who's coming:** only the pilot's characters that can fly a fit in the
  fleet (capability engine, `CharacterFittingReadiness.doctrine_ready`),
  each with only the fits it can fly. The usual fit is picked from past
  fleets (`fleets/helpers/ship_suggestions.py`). Two picked characters on the
  same EVE account (`CharacterAccountMember`) get a warning, not a block,
  because the account grouping is often inferred.
- **Sign up** or **Nevermind, I'm not available**.

## The link

`I'm available` is a bot button, not a link, so Discord tells the bot who
pressed it. The bot calls `POST /api/fleets/invites/{id}/discord-available`
with that Discord user; the API checks the user owns the invite and returns
a link. A forwarded DM or a screenshot has no working link in it.

The token is a Django-signed `{invite id, user id}` (`fleets.invite-rsvp`
salt, `fleets/helpers/invite_rsvp.py`):

- It opens the page for **10 minutes** (`OPEN_MAX_AGE`).
- Opening it returns a fresh `submit_token`, good for **1 hour**
  (`SUBMIT_MAX_AGE`), so a slow pick doesn't lose the answer.
- It can only read and answer that one invite. It is not a login.
- A bad, expired or forwarded token, or a fleet that has started, gets the
  same `410 This link has expired.` and never the fleet's name.

The page is `noindex`, sends `Cache-Control: no-store` and
`Referrer-Policy: no-referrer`, and has analytics turned off, because the
URL is the key.

## API

| Route | Auth | Purpose |
|---|---|---|
| `POST /fleets/invites/{invite_id}/discord-available` | bot | A sign-up link for the pilot who pressed I'm available |
| `GET /fleets/rsvp/{token}` | none | The form: fleet, characters with fits, `submit_token` |
| `POST /fleets/rsvp/{submit_token}` | none | Sign up: `{picks, confidence}`; no picks = available with no ship yet |
| `POST /fleets/rsvp/{submit_token}/not-available` | none | Not available for this fleet |

Signing up replaces the pilot's ships on the fleet through the same code
as the fleet page's picker (`set_my_ship_volunteers`), so Academy fits,
bursts and the private-fleet thread work the same way.

## Confidence

`EveFleetInvite.confidence` is `high`, `medium`, `low` or blank (answered
some other way). **Low** ships don't count toward the fleet's ship targets
(`volunteer_hulls`), and the "Still coming?" re-ping only goes to pilots who
haven't answered, so Low pilots don't get it. The invite DM, once answered,
says "You said you might be 10-15 minutes late" or "You said you might not
make it, so you aren't counted yet".
