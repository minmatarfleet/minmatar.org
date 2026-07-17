# Authentication

Authentication answers "who are you?" Discord is the identity provider; a JWT carries that identity on each request.

## Login flow

```mermaid
sequenceDiagram
    actor Browser
    participant FrontEnd as Front-end (Astro)
    participant BackEnd as Back-end (Django)
    participant DB as Database
    participant Discord

    Browser->>FrontEnd: Get home page
    FrontEnd->>Browser: Home page with login icon
    Browser->>BackEnd: /users/login
    BackEnd->>Browser: Redirect to Discord
    Browser->>Discord: oauth2/authorize
    Discord->>Browser: Redirect to callback with code
    Browser->>BackEnd: /users/callback with code
    BackEnd->>Discord: Exchange code for access token
    Discord->>BackEnd: Access token
    BackEnd->>DB: Save Discord + Django users
    BackEnd->>Browser: Redirect to frontend login with JWT
    Browser->>FrontEnd: /users/login with JWT
    FrontEnd->>Browser: Logged-in page
    Browser->>Browser: Store JWT in cookie
    Browser->>FrontEnd: Request page with data
    FrontEnd->>BackEnd: API request with Bearer JWT
    BackEnd->>BackEnd: Validate JWT (AuthBearer)
    BackEnd->>FrontEnd: JSON content
    FrontEnd->>Browser: HTML content
```

## Components

- **Discord OAuth** — There is no password login. The Discord account creates or links the Django `User`.
- **JWT** (`backend/users/jwt_auth.py`) — Payload includes `user_id`, `username`, `avatar`, and `is_superuser`. The token carries **no permissions or features**; those are evaluated server-side on each request.
- **`AuthBearer`** (`backend/authentication.py`) — Validates the JWT on Django Ninja endpoints and sets `request.user`. `AuthOptional` allows anonymous access where appropriate.
- **EVE characters** — Linked separately via ESI SSO. The **primary character** determines the user's affiliation (see [authorization.md](authorization.md)).

Authentication only identifies the user. Access decisions are authorization.
