# Tribe invitations

A chief asks a pilot into their tribe group. The bot DMs the pilot on
Discord; the pilot opens the invite on the group page, picks characters and
is an active member straight away. There is no application to review.
Wireframes: https://claude.ai/artifact/QYo8NfVSxE12Ps63sFmcsu

## Rules

1. **Who can invite:** anyone who can manage the group
   (`user_can_manage_group`: the group chief, the tribe chief, admins). The
   same check as approving applications.
2. **Who can be invited:** pilots who could apply. `invite_blocker` in
   `backend/tribes/helpers/invitations.py` says why someone can't be:
   already a member, applied (the chief approves instead), already invited,
   declined in the last 30 days, on trial when the group requires off-trial,
   or no `tribes.apply` access.
3. **Joining checks** are the same as applying: off trial when the group
   needs it, and the group's ESI token on every picked character. Skill and
   ship requirements are recorded in `requirement_snapshot`, not enforced.
4. **No review:** accepting sets the membership `active` with the inviter as
   `approved_by`, so membership history and the Discord role sync treat it as
   an approval.
5. **Limits:** one waiting invite per pilot per group, at most 10 pilots per
   send, a note of at most 300 characters. Invites expire after 14 days; a
   declined pilot can be invited again after 30 days.

## Data model

`tribes.TribeGroupInvitation`: `tribe_group`, `user` (the pilot),
`invited_by`, `note`, `status` (`pending`, `accepted`, `declined`,
`withdrawn`, `expired`), `created_at`, `expires_at`, `responded_at`,
`membership` (set on accept). A pending invite past `expires_at` reads as
`expired` before the daily `tribes.tasks.expire_tribe_invitations` sweep
marks it.

## API (`/api/tribes`)

| Method | Path | Who |
|--------|------|-----|
| GET, POST | `/{tribe_id}/groups/{group_id}/invitations` | people who manage the group |
| DELETE | `/{tribe_id}/groups/{group_id}/invitations/{id}` | withdraw a waiting invite |
| GET | `/{tribe_id}/groups/{group_id}/invitations/candidates?q=` | pilot search for the picker |
| GET | `/invitations/mine` | the pilot's waiting invites |
| POST | `/invitations/{id}/accept` | the pilot, with `character_ids` |
| POST | `/invitations/{id}/decline` | the pilot |
| POST | `/invitations/{id}/discord-decline` | the bot, for the DM's Decline button |

## Discord

- `tribes.invited` (Discord and web on): the invite DM. Its embed names the
  inviter, group, note, requirements and expiry. Its buttons replace Mark as
  read: **Open invite** links to the group page; **Decline** is a bot button
  (`tribe_invite:decline:<id>`, in `bot/app/custom_ids.py`).
- `tribes.invite_answered` (Discord on): the inviter hears when the pilot
  joins or declines.
- Once an invite is answered, withdrawn or expires,
  `tribes.tasks.update_tribe_invitation_dm` edits the DM to say what happened
  and removes its buttons.
- A muted or undeliverable DM doesn't block anything: the invite still shows
  on the group page, and the chief's list says "DM not delivered" with Copy
  invite link.

## Website

- Manage membership (`/alliance/tribes/<t>/<g>/members`): **Invite pilots**
  opens the picker (`ButtonInvitePilots`, search results from
  `tribe_invitation_candidates_component`); the Invitations list
  (`tribe_group_invitations_component`) sits between requests and members.
- Group page: a waiting invite shows above the tabs
  (`TribeGroupInvitationBanner`). Join opens the apply dialog in invite mode;
  accepting reloads the page.
