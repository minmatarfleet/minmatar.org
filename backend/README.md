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
The backend Python code includes three main external integrations...

1. The database
2. ESI, the Eve Swagger Interface 
3. Discord

In many cases the Django data entities have signals registered that call ESI, Discord or both, 
when changes are made to the database. The signals are not necessarily defined in the same 
package as the entities they are attacjed to.

Due to the deeply interconnected nature of the various parts of the code, the most challenging
aspects of unit testing are generally setting up the necessary test data and mocks, and disabling
signals.

Many of the `TestCase` classes provide helper functions for setting up test data and disabling signals, 
though this is not yet done in a systematic manner.

Mocking of the Discord and ESI clients allows testing of the code without external connectivity to those services. 
The mocks are created using standard Python mocking/patching mechanics.

Note that not all ESI access is performed via the mockable `EsiClient` yet. 
While it is technically possible to mock the existing code, it is much easier to migrate it to use `EsiClient` first.

Because they are invariably mocked in unit tests, the Discord and ESI
client classes are excluded from coverage reporting. 
As they cannot be easily tested, they should contain minimal logic.

Some of the background Celery tasks identify a set of entities and then create another asynchronous task instance for each
of those entities. The outer tasks are therefore generally not tested.

You can also use an annotation to disable signals for a test...
```
import factory
from django.db.models import signals

@factory.django.mute_signals(signals.pre_save, signals.post_save)
```

### Standalone backend server

The backend can run as a standalone server using an embeded sqlite database.

To configure this, the Django settings have the following values...

```
SECRET_KEY=testing
FAKE_LOGIN_USER_ID=1
MOCK_ESI=True
```

In this mode it will automatically create an initial admin user on startup
and display the JWT token for that test user.

Attempts to log in will bypass the Discord login process with that fake user.

Calls to the Eve Swagger Interface (ESI) will be mocked.

## Commands
### Set local environment variables
```for x in $(sed -e 's/#.*//' .env.local | grep '=') ; do export $x ; done``` 

### Run tests with result and coverage reporting
```
coverage run -m manage test --testrunner="testrunner.Runner"  && cat testresults.txt && coverage html
```

### Setup test data
```
./manage.py shell --command="from tech.testdata import setup_test_data; setup_test_data()"
```

### Create a test admin user and display JWT
```
./manage.py shell --command="from authentication import make_test_user; make_test_user(101, 'Tester 1', True)"
```

## Code cleanup tasks

* Remove `EveFleetLocation`, `EveFreightLocation` and `EveMarketLocation`
* Remove `EvePrimaryCharacter`
* Remove `EveCharacter.tokens` property
* Remove `EveCharacter.is_primary`