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

## Making a standalone test user
It is also possible to make and use a standalone test
user that doesn't use Discord for authentication.

```
python manage.py shell_plus
```
Then...
```
from authentication import make_test_user
make_test_user(101, "Tester 1", True)
```
replacing parameters (user ID, user name, is SuperUser) as appropriate.

Copy the JWT bearer token.

Run the backend server, and browse to the API documentation page. Click the Authorize button,
paste the token you copied above, and click Authorize.

You should now be able to test the APIs as if you were logged in as that user.

Note that this only works if you have access to the server's secret key.

Also note that some APIs require Discord for correct operation regardless of authentication.

## Testing
The backend Python code includes three primary external integrations...

1. The database
2. ESI, the Eve Swagger Interface 
3. Signal

In many cases the Django data entities have signals registered that call ESI, Signal or both, when changes are made to the database.

Many of the unit tests disable these signals.

In other cases, the Discord and ESI clients are mocked.

## Commands
- `for x in $(sed -e 's/#.*//' .env.local | grep '=') ; do export $x ; done` set local environment variables