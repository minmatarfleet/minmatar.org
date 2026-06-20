# Minmatar Mobile (PoC)

React Native proof-of-concept for [my.minmatar.org](https://my.minmatar.org/), built with Expo and React Native Paper.

## Features

- **Pulse** — Curated briefing: tonight/weekend fleets, warzone hot systems (mock), latest headline + AAR
- **News** — All published posts with All / Propaganda filter
- **Activity** — Unified feed of live fleets, kill bursts, FC comms, and militia movement (mock)
- **Fleets** — Full schedule via “See all fleets” on Pulse (linked account required; not in tab bar)

## Run

```bash
cd mobile
npm install
cp .env.example .env
npm run start:tunnel
```

Then open in **Expo Go** on your phone (scan the QR code). The project targets **Expo SDK 54**.

Use `npm run web` for browser testing. On **WSL2**, use `start:tunnel` so your phone can reach the dev server.

### Tunnel troubleshooting

`--tunnel` requires **`@expo/ngrok`** (included in devDependencies). After `npm install`, run:

```bash
npm run start:tunnel
```

If you see `Cannot read properties of undefined (reading 'body')`, run `npm install` again to ensure `@expo/ngrok` is present. If tunnel still fails (ngrok outage or rate limits), use LAN + your own tunnel:

```bash
npm run start:lan
# separate terminal: ngrok http --host-header=localhost 8081
# export EXPO_PACKAGER_PROXY_URL=https://YOUR-NGROK-URL
```

Ensure port **8081** is free before starting (`fuser -k 8081/tcp` if a stale Metro process is holding it).

## Authentication (EVE SSO)

Login uses production **`https://api.minmatar.org`** by default (`EXPO_PUBLIC_API_URL`).

1. Landing screen → **Log in with EVE Online**
2. Flow: `App → /api/users/login/eve → EVE SSO → /api/users/eve/complete → auth/callback?token=…`
3. JWT includes **`character_id`**. If the character is linked on my.minmatar.org, it also includes **`user_id`** (required for fleet schedule).

## Data sources

| Feature | Source |
|---------|--------|
| News, post detail | `GET /api/blog/posts` (public) |
| Fleets, fleet detail | `GET /api/fleets/v3` (auth + linked account) |
| Doctrine on fleet detail | `GET /api/doctrines/{id}` (public) |
| Warzone on Pulse | `GET /api/feed/warzone` — contested cards + 24h changes table |
| Activity feed | `GET /api/feed` (public) |

**Warzone data:** requires migration `feed.0007_feed_system_contested_snapshot` and the hourly Celery task `[Feed] Poll FW contested %` (runs at `:50`). The changes table compares the latest reading to the oldest snapshot within the last 24 hours — no full day of history required.

Local dev fake deltas:

```bash
cd backend
pipenv run python manage.py seed_warzone_contested_dev --clear
```

## Stack

- [Expo SDK 54](https://expo.dev/) + [Expo Router](https://docs.expo.dev/router/introduction/)
- [React Native Paper](https://callstack.github.io/react-native-paper/) with Minmatar dark theme
- Fonts: Norwester (headings), Montserrat (body)
