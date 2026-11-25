---
name: mumble-voice
description: >-
  Use, administer and debug fleet voice on Mumble in production: the Murmur
  server (voice-murmur), the authenticator (voice-auth), the celery-voice
  worker, /voice sign-in, certificates, channels and leases. Use when someone
  can't connect to Mumble, voice is down or hanging, "no heartbeat",
  voice_status, InvalidCallbackException, a pilot needs their certificate
  reset or kicked, the voice certificate renews, or the voice option needs
  turning on or off.
---

# Mumble voice

Design: [docs/mumble-architecture.md](../../../docs/mumble-architecture.md). Service internals and the hang guards: [voice/README.md](../../../voice/README.md). Commands run on the prod host from /home/minmatar/minmatar.org, in the same form as the [production-command](../production-command/SKILL.md) skill.

```bash
DC="docker compose -f docker-compose-prod.yml"
```

## How it fits together

| Piece | What it is |
|---|---|
| voice-murmur | Murmur (mumblevoip/mumble-server, pinned with voice/MumbleServer.ice). Public port **64738** tcp+udp. Ice on :6502, only on the internal voice network. Data (sqlite, channels) in the voice_murmur volume. |
| voice-auth | Our Ice client. Registers the authenticator (callback :6503), builds channels and ACLs (layout.py), reconciles every 5 s (reconcile.py), pushes the Let's Encrypt certificate (certs.py). Reads records from Redis db 3, falls back to Django through edge:8001/api/voice/internal/. |
| celery-voice | Django side: publishes records to Redis, expires leases, heartbeat_check. |
| app | /voice sign-in (EVE SSO, publicData only, the one registered callback), connect tokens, certificates API, voice_status. |
| Fleet voice option | fleets.FleetVoiceOption row kind="mumble". is_active turns Mumble on for fleets; Discord stays the default. |

voice.minmatar.org is only the address the Mumble client connects to (port 64738). It is not a website: a browser on it gets nginx's default page. The voice page is https://my.minmatar.org/voice.

## How pilots connect and stay connected

1. Mumble's first-run certificate wizard makes a client certificate. Pilots must accept it.
2. /voice gives a mumble://name:token@voice.minmatar.org link with a **one-time** token.
3. The first connect redeems the token and **binds the client certificate** to the character.
4. Every later connect is decided by the certificate alone. Reconnecting from the server list needs no token and no password.

- No server password for pilots. SuperUser is always refused by the authenticator.
- New PC, reinstall or lost certificate: get a fresh link from /voice and connect once; each device binds its own certificate.
- A certificate bound to a character that is no longer the account's main is refused; a fresh token moves it (same account only).
- Pilots see and revoke their certificates on /voice (revoking also kicks that session).
- Declined the wizard (no certificate): nothing can bind, so every connect needs a fresh link.

## First look (read-only)

```bash
$DC ps --format "{{.Service}} {{.Status}}" | grep voice
$DC exec -T app python3 manage.py voice_status
$DC logs --since 30m voice-auth | grep -v -E '^\S+\s+\|\s*[{}]?\s*$' | tail -40
$DC logs --since 30m voice-murmur | grep -v "voice thread" | tail -40
```

Healthy looks like: voice-auth ... (healthy), voice_status ends Voice service: healthy with a recent Heartbeat:, and voice-auth has logged Voice service connected; authenticator registered and Loaded the voice server certificate.

Reading Murmur's connect lines:

| Murmur log | Meaning |
|---|---|
| New connection then Client version … then Authenticated | Normal login. voice-auth logs Voice login accepted (ok). |
| Rejected connection … Wrong certificate or password | The authenticator refused (voice-auth logs refused (<reason>): unknown = spent/invalid token and no bound certificate, no_identity, superuser). Send the pilot to /voice for a fresh link. |
| Client version … and then nothing | Murmur is frozen. See "Murmur stops answering". |
| <name> not allowed to Enter in <channel> | ACLs working as designed (the pilot isn't in that fleet/branch). Fleet 1's subchannels are open to every community member; Fleet 2 and 3 are fleet only. |
| Connection closed: The remote host closed the connection | The client left or timed out. |

## Diagnose by symptom

### Can't connect at all

1. From outside, the port is open: nc -vz -w 5 voice.minmatar.org 64738.
2. Something is listening: ss -lntup | grep 64738 shows docker-proxy.
3. Murmur logs show the attempt (above). No line at all means the client never reached the server: wrong host or port in the client, or a network problem on their side.

### "no heartbeat" in voice_status

voice-auth writes voice:heartbeat (Redis db 3, ex=300) on every pass of its main loop. A missing key means the loop is stuck or the service is down, even if /health once said healthy.

```bash
$DC exec -T redis redis-cli -n 3 ttl voice:heartbeat      # -2 = missing
```

### Murmur stops answering (logins hang after "Client version")

Murmur waits on the authenticator from its main thread, so the two can freeze each other. The guards (Ice call timeouts, a 5 s login deadline, a stall watchdog that dumps stacks and exits) are described in [voice/README.md](../../../voice/README.md). If it still hangs:

1. Capture stacks **before** restarting: docker kill -s USR1 $($DC ps -q voice-auth), then read $DC logs --tail 200 voice-auth.
2. Check whether Murmur answers Ice at all (read-only probe, 8 s timeout):

   ```bash
   $DC exec -T voice-auth python3 - <<'EOF'
   import sys; sys.path.insert(0, "/opt/voice")
   from voice_auth import main, config
   main.load_slice()
   import Ice, MumbleServer
   cfg = config.from_env()
   c = Ice.initialize(["--Ice.Default.EncodingVersion=1.0", "--Ice.Default.InvocationTimeout=8000"])
   ctx = {"secret": cfg.ice_secret}
   try:
       m = MumbleServer.MetaPrx.checkedCast(c.stringToProxy(f"Meta:tcp -h {cfg.ice_host} -p {cfg.ice_port}"), ctx)
       print("murmur users:", len(m.getServer(cfg.server_id, ctx).getUsers(ctx)))
   except Exception as e:
       print("murmur probe failed:", type(e).__name__)
   finally:
       c.destroy()
   EOF
   ```

   InvocationTimeoutException means Murmur is frozen.
3. Recover (state change, ask first; it drops everyone connected): $DC restart voice-murmur voice-auth. voice-auth may log one ConnectionRefusedException while Murmur boots, then authenticator registered.
4. Open an issue with the stack dump: a hang that the guards didn't catch is a bug.

### voice-auth loops on InvalidCallbackException

Murmur can't reach the callback voice-auth published. The adapter must listen on 0.0.0.0 and publish the service name (configure_properties in voice_auth/main.py), because voice-auth is on two networks and Murmur only on voice. Check reachability from Murmur:

```bash
$DC exec -T voice-murmur bash -c 'timeout 3 bash -c "</dev/tcp/voice-auth/6503" && echo OPEN || echo CLOSED'
```

### voice-murmur stuck in "Created": port is already allocated

Something else holds 64738, for example an old Mumble stack. ss -lntup | grep 64738 and docker ps show what. The deploy (scripts/deploy.sh) runs up -d on every service and fails while this lasts.

### Certificate problems

voice-auth runs as a non-root user and reads /etc/letsencrypt/live/voice.minmatar.org/ (mounted read-only). The host grants the image's group read access, once:

- live/ and archive/: group = the image's gid, mode 0710
- live/voice.minmatar.org and archive/voice.minmatar.org: 0750
- archive/voice.minmatar.org/privkey*.pem: 0640

Certbot keeps the group and mode on renewal. Check from the container:

```bash
$DC run --rm --no-deps --entrypoint id voice-auth            # the gid
$DC run --rm --no-deps --entrypoint sh voice-auth -c 'head -c 27 /etc/letsencrypt/live/voice.minmatar.org/privkey.pem'   # -----BEGIN PRIVATE KEY-----
```

After a renewal voice-auth logs Loaded the voice server certificate within a minute. If Murmur still shows its own self-signed certificate (clients warn), the authenticator never connected. Fix that first.

## Administration

All of these change state: say what will happen and get a yes first.

| Task | Command |
|---|---|
| Republish every record to Redis and show status | $DC exec -T app python3 manage.py voice_status --rebuild |
| Turn Mumble on or off for fleets | $DC exec -T app python3 manage.py shell -c 'from fleets.models import FleetVoiceOption as O; print(O.objects.filter(kind="mumble").update(is_active=True))' (False to turn off; never change is_default without asking) |
| Kick or reset a pilot's certificate | Revoke it from the website's certificate API (DELETE /api/voice/certificates/{id}, what /voice uses). It unpublishes the certificate and kicks the session. |
| Restart voice | $DC restart voice-murmur voice-auth (drops everyone connected) |
| Force a certificate renewal (testing the reload) | certbot renew --cert-name voice.minmatar.org --force-renewal (counts against Let's Encrypt's weekly duplicate limit) |

Channels and ACLs come from voice_auth/layout.py and are applied at every voice-auth start. Change them in code, not in a Mumble client. Fleet commanders get Whisper in their fleet's Command channel, inherited downward; an FC talks to the whole fleet with a shout key set to "Current channel + Subchannels".

## Rules

- Never print .env or secret values (VOICE_ICE_SECRET*, VOICE_INTERNAL_SECRET, VOICE_SUPERUSER_PASSWORD, the server password). Check presence with test -n "$VAR" inside a container, never env or docker compose config without -q.
- Don't log in as SuperUser or change channels by hand: voice-auth owns the layout and will fight manual edits.
- Don't delete the voice_murmur volume or Murmur's sqlite: it holds the server's state and its user ids.
- Restarts, option toggles, renewals and anything under /etc/letsencrypt are state changes: ask first.
- The repository is public: no pilot names, certificate hashes, IPs or log excerpts with them in issues or pull requests.
