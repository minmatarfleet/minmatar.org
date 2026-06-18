# Minmatar Mobile (PoC)

React Native proof-of-concept for [my.minmatar.org](https://my.minmatar.org/), built with Expo and React Native Paper.

## Features

- **Home** — Alliance news and blog posts (mock data)
- **Fleets** — Upcoming and active fleets (mock data)

## Run

```bash
cd mobile
npm install
npm run start:tunnel
```

Then open in **Expo Go** on your phone (scan the QR code). The project targets **Expo SDK 54**, which is compatible with the App Store version of Expo Go.

Use `npm run start` for local web/emulator only. On **WSL2**, use `start:tunnel` so your phone can reach the dev server.

Press `w` for web, `a` for Android emulator.

### Expo Go stuck on "opening project"?

This usually means your phone cannot reach the Metro bundler.

**WSL2 (most common):** Use tunnel mode so Expo routes traffic through the internet instead of your LAN:

```bash
npm run start:tunnel
```

Scan the **new** QR code after the tunnel URL appears (it can take 15–30 seconds to connect).

**Native Windows/macOS:** Ensure phone and computer are on the same Wi‑Fi, then try:

```bash
npm run start:lan
```

If it still hangs, allow inbound TCP port **8081** in your firewall.

### DevTools error as root?

If you see `Running as root without --no-sandbox`, ignore it — the app still runs. The npm scripts set `EXPO_NO_DEVTOOLS=1` to suppress it.

## Authentication (EVE SSO)

Login uses the same **django-esi** flow as the web app — one EVE callback URL (`/sso/callback`), no extra ESI app registration needed.

1. Copy env:

```bash
cp .env.example .env
```

Set `EXPO_PUBLIC_API_URL` to a URL your phone can reach (LAN IP or `https://api.minmatar.org`).

2. Tap **Log in** in the header. Flow:

```
App → /api/users/login/eve → EVE SSO → /sso/callback → /api/users/eve/complete → mobile://auth/callback?token=…
```

3. The JWT always includes **`character_id`** (and `character_name`). If the character is linked on my.minmatar.org, it also includes **`user_id`**. You can add custom backend logic later once you know who logged in.

Uses the backend `ESI_SSO_CLIENT_ID` / `ESI_SSO_CLIENT_SECRET` from `.env` — secrets never go in the app.

## Stack

- [Expo SDK 54](https://expo.dev/) + [Expo Router](https://docs.expo.dev/router/introduction/)
- [React Native Paper](https://callstack.github.io/react-native-paper/) with Minmatar dark theme
- Fonts: Norwester (headings), Montserrat (body)

## Out of scope (PoC)

Real API integration for news/fleets feeds (still mock data). Detail screens use mock data.
