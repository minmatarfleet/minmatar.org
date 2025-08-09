
# Developer Data Seeding Guide

Setting up a fully functional development environment for the Minmatar.org backend requires more than just running the quick start. This guide will walk you through the process of seeding your development database and configuring your environment so you can work with all features enabled.

## Prerequisites

Before proceeding, ensure you have completed the following, as described in other documents

1. **Backend Setup:** Follow the instructions in `backend/README.md` to get the backend running with an empty database.
2. **Discord Integration:** Complete the Discord setup as described in the documentation.
3. **ESI Application:** Create and configure an ESI application. Add the credentials to your `.env` file.
4. **Database & Redis:** Ensure both your database and Redis are running.
5. **Database Migrations:** Run migrations to create the necessary tables: `python manage.py migrate`
6. **Stop All Services:** Make sure the backend, Celery, Beat, Bot, and Frontend are **not** running during the seeding process.

**note** all steps describing running shell commands should be in the backend folder with pipenv activated and environment variables set in the session.

```sh
cd backend
pipenv shell
set -a; source .env; set +a
```
---

## Step 1: Create a Developer User and API Token

You'll need a superuser for API access and Discord bot integration.

1. Open a django shell:
    ```sh
    python manage.py shell_plus
    ```
2. In the Django shell, run:
    ```python
    from authentication import *
    make_test_user(uid=1, user_name="Dev Super User", is_super=True)
    ```
3. Copy the generated token that is printed out and add it to `bot/.env` as `MINMATAR_API_TOKEN`.

    - The Discord bot uses this token to authenticate local API calls (e.g., for slash commands like `/timer`).
    - You can also use this token to log in to the backend API web UI by pasting it in the "Bearer token" box under "Authorize".

---

## Step 2: Sync Discord Roles

Site permissions and roles are managed via Discord. Sync roles from Discord to Django:

1. Open the Django shell:
    ```sh
    python manage.py shell_plus
    ```
2. Run:
    ```python
    from discord.tasks import *
    import_external_roles()
    ```
    - This pulls roles from Discord to the database and then creates corresponding Django groups.

---

## Step 3: Seed Development Data

Now, seed the database with development data. This step depends on roles being synced.

1. In the Django shell:
    ```sh
    python manage.py shell_plus
    ```
2. Run:
    ```python
    from tech.seed_data import *
    seed_database_for_development()
    ```
    - This will populate the database with test users, organizations, characters, and other essential data for development.
    - To dig in to what exactly it does, please read the code in tech.seed_data

---

## Step 4: Start All Services

Assuming the data seed completed successfully, you can now start the Backend, Celery, Beat, UI, and Bot as usual.

---

## Step 5: Initial User Setup

1. **Login as Admin Discord User:** Use your Discord admin account to log in to the site.
2. **Register a Main Character:** Pick a character in the "FL33T" alliance.
3. **Promote to Superuser:** In the Django shell:
    ```sh
    python manage.py shell_plus
    ```
    ```python
    from django.contrib.auth.models import User
    u = User.objects.get(id=2)  # ID 2 if you followed the steps above
    u.is_superuser = True
    u.save()
    ```
4. **Access the Admin Console:** Visit [http://localhost:8000/admin/](http://localhost:8000/admin/).

    - If you have issues logging in, try a different browser or use private browsing mode.

---

## (Optional) Step 6: Add a Second User

To test multi-user features:

1. Open a different browser or a private window.
2. Log in to Discord with a second account.
3. Log in to the dev web UI with this account [http://localhost:4321](http://localhost:4321).
4. Register a main character (choose another character in FL33T as a second main).

---

## Step 7: Run Background Tasks

In production, background tasks are scheduled. For development, you can run them manually as needed. These include:

- Updating character affiliations
  - this gets your characters in to the alliance role
- Syncing Discord users and nicknames
- Fetching public contracts

```sh
python manage.py shell_plus
```
```python
from discord.tasks import *
from eveonline.tasks import *
from groups.tasks import *
from market.tasks  import *
update_character_affilliations()
update_affiliations()
sync_discord_users()
sync_discord_user_nicknames()
fetch_eve_public_contracts()
```

---

## Step 8: Verify Discord Integration

- Ensure your character is in the alliance and can see the appropriate channels.
- Check that your nickname is set (note: nickname sync will not work for the server admin account).
- Confirm you are in the correct corp chat channel (e.g., "rattini" for certain corps only).

---

## Troubleshooting

- If you encounter issues with admin login or Discord integration, review your `.env` settings and ensure all services are running.
- For advanced debugging, consult the backend and Discord logs.

---

**Happy developing!** If you have suggestions for improving this process, please update this document or reach out to the team.

The seed data script is a work in progress, some areas of it maybe should be part of the main code base, or others might be covering bugs. We can improve this over time.

