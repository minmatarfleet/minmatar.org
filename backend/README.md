# Minmatar.org Backend

## Important URLs
1. [Discord Developer Application](https://discord.com/developers/applications)
1. [EVE Developer Application](https://developers.eveonline.com/)
1. [Django](https://www.djangoproject.com/)
1. [Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)


## Quickstart
1. Create a `.env` file from `.env.example`
1. Create a `.env.local` file from `.env` and update the database host to `127.0.0.1` (see commands below)
1. Create a local Python shell environment `pipenv shell`
1. Install dependencies `pipenv install`
1. Install developer dependencies `pipenv install --dev`
1. Run the database and redis `docker-compose up -d`
1. Migrate the database `python3 manage.py migrate`
1. Run the application `python3 manage.py runserver`

Navigate to `/api/docs` for endpoints or `/admin` for the admin panel.

## Setting your user as admin
```python
python3 manage.py shell_plus
user = User.objects.all()[0]
user.is_superuser = True
user.is_staff = True
user.save()
```

## Commands
- `for x in $(sed -e 's/#.*//' .env.local | grep '=') ; do export $x ; done` set local environment variables