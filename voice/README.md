# Voice service

The Mumble side of fleet voice (design: [docs/mumble-architecture.md](../docs/mumble-architecture.md)). It runs next to Murmur (`voice-murmur` in `docker-compose-prod.yml`) and talks to it over Ice on the internal `voice` network.

Django decides who may connect (`backend/voice/`); this service obeys. It holds no business rules: it reads the access records Django publishes to Redis.

| Path | Role |
|---|---|
| `MumbleServer.ice` | The Ice interface, pinned to the Murmur image (`mumblevoip/mumble-server:v1.5.939`). Update both together. |
| `voice_auth/main.py` | Ice setup, authenticator registration, reconnect loop. The only Ice-specific code. |
| `voice_auth/authenticator.py` | The login decision: bound certificate, else one-time token; `-1` refuse, `-3` try later. `SuperUser` always refused; an empty certificate hash never matches. |
| `voice_auth/records.py` | Reads records from Redis; on a miss asks Django's `/api/voice/internal/` through the edge's `internal` entrypoint. |
| `voice_auth/reconcile.py` | Every 5 s and on `voice:changed`: lease ends, website kicks, branch groups, one-time placement, priority speakers. |
| `voice_auth/layout.py` | The channels and ACLs, applied idempotently at start. |
| `voice_auth/certs.py` | Loads the Let's Encrypt certificate with `updateCertificate`, again whenever certbot renews it. |
| `voice_auth/health.py` | `/health` for the Docker healthcheck, and the `voice:heartbeat` key Django's `voice.tasks.heartbeat_check` watches. |

## Tests

```bash
cd voice && python3 -m unittest discover -s tests -t .
```

They run against a fake Murmur and a fake Redis, and read the contract files in `tests/contracts/`, which the backend writes (`backend/voice/tests/test_publisher.py`; regenerate with `UPDATE_CONTRACTS=1`). No Ice or Redis install is needed.
