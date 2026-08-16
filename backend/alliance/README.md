# Alliance app

Staff alliance health dashboard (`/alliance/health`) and API (`/api/alliance/health/`).

Endpoints: `overview`, `attention`, `trials`, `leave`, `corporations`, `cohorts`.
Hourly snapshot includes MAP, quiet pilots, corp health, cohorts, and trial/leave hygiene.

## Deploy

```bash
cd backend
pipenv run python manage.py migrate alliance
pipenv run python manage.py sync_pilot_features
pipenv run python manage.py refresh_alliance_health
```

Celery beat refreshes the snapshot hourly (`alliance.tasks.refresh_alliance_health_snapshot` at minute 25).

Permission `alliance.view_alliancehealth` is granted to **People Team**, **Technology Team**, and **Tribe - Chief** by migration `0002`. Feature code: `alliance.health`.

Trial/leave lists are read-only on the dashboard. Apply status changes via admin bulk-upload after review. CSV export: `GET /api/alliance/health/trials?bucket=approve&format=csv` and `GET /api/alliance/health/leave?format=csv`.
