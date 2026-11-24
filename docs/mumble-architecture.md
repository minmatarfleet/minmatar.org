# Fleet voice on Mumble

Fleets talk on Discord by default. An FC can pick **Mumble** as a fleet's voice when scheduling; that fleet then gets a channel branch on one alliance Mumble server (`voice.minmatar.org`), and its MOTD links `my.minmatar.org/voice`. Design and decisions: issue #3154. The old, removed stack is in [archive/mumble-removed-stack.md](archive/mumble-removed-stack.md).

**Django decides, the voice service obeys.** Every access rule lives in `backend/voice/access.py`. The voice service (`voice/`) only reads the records Django publishes to Redis and applies them to Murmur over Ice.

```mermaid
flowchart LR
  app[Django app] -->|publish records| redis[(redis db 3)]
  worker[celery-voice] -->|grants, leases| redis
  auth[voice-auth] -->|read| redis
  auth -->|on a miss: /api/voice/internal/| edge[edge, internal entrypoint]
  edge --> app
  murmur[voice-murmur] <-->|Ice, voice network only| auth
  client[Mumble clients] -->|64738 tcp/udp| murmur
```

## Going live

The Mumble voice option (`FleetVoiceOption`, kind `mumble`) is created **inactive** by `fleets/migrations/0069_seed_voice_options.py`, so nothing changes for pilots until ops switches it on in the admin. Before that: the host steps in the private runbook (nginx block and certbot certificate for `voice.minmatar.org`, network protection for port 64738), the secrets in `.env` (see `.env.example`), and removing any old voice stack. `voice.tasks.heartbeat_check` stays quiet until the option is active.

## Who can connect

Worked out on read (`voice_record(character_id)`), never stored:

| Access | Source | Gives |
|---|---|---|
| Community | feature `voice.join` (Alliance, Associate) | Lobby, Open 1-2 |
| Fleet commander | feature `voice.commander` (`pulse.fleet-commanders`) | Commanders in every Mumble fleet branch |
| Capitals on standby | active member of any active group of tribe `capitals` | `capitals` in every branch |
| Campaign ally | a character, corporation or alliance listed as an ally of the fleet's active campaign (factions never count) | that fleet's branch |
| Voice admin | feature `voice.admin` (superusers) or a Strategic FC | `voiceadmin`: move, mute, kick anywhere |
| Ban | `VoiceBan` | refuses everything; checked first |

**Main only.** A character on a site account connects only when it is that account's main (`voice.access`): an alt is refused (`reason: not_main`) even through the guest sign-in, and fleet grants earned on an alt (in the in-game fleet, volunteering, boss) go to the main. Characters with no site account count as their own main.

Stored as `VoiceGrant` rows (`backend/voice/grants.py`), so logins never join fleet tables: pilots in the in-game fleet (logistics hull and wing noted for placement), volunteers, invitees who said in (except low confidence), the fleet's creator and in-game boss (with their alts) as commanders, co-FCs added on the fleet page, and capital hulls flown or volunteered by trusted pilots. Each sync also expires the grants of pilots who backed out (withdrew, answered Out or low confidence, left the in-game fleet); co-FC grants are only changed on the fleet page. Grants all end with the fleet's lease. A kick lasts for the rest of the lease.

## Leases

Three branches (`Fleet 1`-`Fleet 3`) always exist. `backend/voice/leases.py`: a Mumble fleet leases a free branch when tracking starts, or from 2 hours before start once it has signups. With no tracking 30 minutes after start, or 30 minutes after it closes, or when the FC switches voice away from Mumble, the lease ends; the voice service kicks whoever is left and resets the branch. `voice.tasks.expire_grants` runs every minute; the 30-second fleet poll queues `voice.tasks.sync_fleet_grants` for Mumble fleets only.

## Signing in

- `/voice` (`frontend/app/src/pages/voice.astro`) has no gate. Site members use their own session and connect as their main. Guests sign in with EVE: `/voice/sign-in` sets a random state in a short-lived cookie and sends the browser to `GET /api/voice/login` (`publicData` only, no site account), and `/voice/login` keeps the returned token only when its state matches the cookie; `backend/voice/views.py` completes it, stores a `VoiceIdentity` (with the owner hash) and keeps no ESI token. The browser gets a voice JWT (`aud: voice`, 30 days) in an HttpOnly `voice_session` cookie. A changed owner hash (character sold) revokes certificates and grants.
- **Connect** (`POST /api/voice/connect`) mints a one-time token (hashed, 2 minutes) inside a `mumble://` link. The first login binds the client certificate; later logins use it. An empty certificate hash is never bound or matched. Up to 3 certificates per character, removable on `/voice`. A certificate bound to the account's old main moves to the new main on its first Connect; one bound to another account is refused.
- The Mumble user id is the `VoiceIdentity` id. Display name `[TICKER] Character`. `SuperUser` is always refused.
- **Fail closed**: Murmur has a long random server password nobody is told. With the voice service down, nobody gets in (lab-verified, `voice/tests/lab/fail_closed.py`).

## Redis contract

Written by `backend/voice/publisher.py`, read by `voice/voice_auth/records.py`, pinned by `voice/tests/contracts/*.json` (regenerate with `UPDATE_CONTRACTS=1` from `backend/voice/tests/test_publisher.py`; keep changes additive).

| Key | Value |
|---|---|
| `voice:char:<character_id>` | the record: admitted, banned, display name, server groups, per-branch groups and placement, preferred branch |
| `voice:identity:<id>` | character id |
| `voice:cert:<hash>` | identity id |
| `voice:leases` | branch -> lease id, fleet id, wing channels |
| `voice:changed` | pub/sub: a character id, `leases` or `commands` |
| `voice:commands` | list of website kicks |
| `voice:heartbeat` | written by the voice service; watched by `voice.tasks.heartbeat_check` |

`voice.tasks.rebuild_records` republishes everything hourly, and `expire_grants` rebuilds when Redis lost records. `manage.py voice_status [--rebuild]` shows leases and the heartbeat.

## The server

- Channels and ACLs: `voice/voice_auth/layout.py`. Root, Lobby (default channel), Open 1-2, and per branch: Command at the top, Mainline, Logistics, Auxiliary A-C below. Text is off; nobody gets `Ban` or `Write` (Ban shows IP addresses). Commanders are priority speakers.
- Placement (`voice/voice_auth/reconcile.py`): once per lease, by role (Command, Logistics, the FC's wing mapping, else Mainline); reconnects return to the last channel; a pilot's own moves are never overridden and nobody is pulled out of an Open channel or another fleet's branch.
- Compose (`docker-compose-prod.yml`): `voice-murmur` (pinned image, settings as `MUMBLE_CONFIG_*`), `voice-auth` (built from `voice/`), `celery-voice`. The `voice` network is internal and carries only Ice. `/api/voice/internal/` is served only on the edge's `internal` entrypoint (no host port) and checks `VOICE_INTERNAL_SECRET`. Ordinary deploys don't recreate the voice services.
- Hangs: calls into Murmur time out after 10 s, login decisions after 5 s, and a watchdog exits voice-auth when its main loop stalls for a minute so `restart: always` brings it back (`voice/README.md`, "When Murmur stops answering").
- Tests: `voice/tests/test_service.py` (fake Murmur) and the real-Murmur lab, `voice/tests/lab/run.sh`, both in the `voice-check` CI job.
