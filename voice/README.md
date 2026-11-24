# Voice service

The Mumble side of fleet voice (design: [docs/mumble-architecture.md](../docs/mumble-architecture.md)). It runs next to Murmur (`voice-murmur` in `docker-compose-prod.yml`) and talks to it over Ice on the internal `voice` network.

Django decides who may connect (`backend/voice/`); this service obeys. It holds no business rules: it reads the access records Django publishes to Redis.

Operating and debugging it in production: the mumble-voice skill (`.claude/skills/mumble-voice/SKILL.md`).

| Path | Role |
|---|---|
| `MumbleServer.ice` | The Ice interface, pinned to the Murmur image (`mumblevoip/mumble-server:v1.5.939`). Update both together. |
| `voice_auth/main.py` | Ice setup, authenticator registration, reconnect loop. The only Ice-specific code. |
| `voice_auth/authenticator.py` | The login decision: bound certificate, else one-time token (also tried when the certificate's record is refused, so a new main can take over its certificate); `-1` refuse, `-3` try later. `SuperUser` always refused; an empty certificate hash never matches. |
| `voice_auth/records.py` | Reads records from Redis; on a miss asks Django's `/api/voice/internal/` through the edge's `internal` entrypoint. |
| `voice_auth/reconcile.py` | Every 5 s and on `voice:changed`: lease ends, website kicks, branch groups, one-time placement, priority speakers. |
| `voice_auth/layout.py` | The channels and ACLs, applied idempotently at start. |
| `voice_auth/certs.py` | Loads the Let's Encrypt certificate with `updateCertificate`, again whenever certbot renews it. |
| `voice_auth/health.py` | `/health` for the Docker healthcheck, the `voice:heartbeat` key Django's `voice.tasks.heartbeat_check` watches, and the watchdog that exits a stalled process. |

## When Murmur stops answering

Murmur calls the authenticator on its main thread and waits for the answer with no timeout; every Ice call we make into Murmur also needs that thread. So a login decision that never comes back freezes Murmur, and a frozen Murmur freezes our main loop. Guards:

- Every call into Murmur gives up after `VOICE_ICE_TIMEOUT_MS` (10 s, `Ice.Default.InvocationTimeout`). The loop then destroys the communicator, which also fails any login Murmur is still waiting on, and reconnects.
- A login decision answers within `VOICE_AUTH_DEADLINE_SECONDS` (5 s); a slow Redis or Django, or an unexpected error, becomes "try again later" (-3). The Ice server thread pool has 4 threads, so one slow decision doesn't queue the next.
- `/health` answers 503 once the main loop hasn't finished an iteration for `VOICE_STALL_SECONDS` (3 ticks, at least 60 s). The watchdog then dumps every thread's stack and exits; `restart: always` brings it back. Docker never restarts a container that is only unhealthy.

Diagnosing a hang: `docker kill -s USR1 <voice-auth container>` prints every thread's Python stack to the logs. `VOICE_LOG_LEVEL=DEBUG` logs each Ice call to Murmur with its duration.

## Tests

```bash
cd voice && python3 -m unittest discover -s tests -t .
```

They run against a fake Murmur and a fake Redis, and read the contract files in `tests/contracts/`, which the backend writes (`backend/voice/tests/test_publisher.py`; regenerate with `UPDATE_CONTRACTS=1`). No Ice or Redis install is needed.
