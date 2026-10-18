# Run the backend tests the way CI does (.github/workflows/pr-check.yml).
# SETUP_TEST_DATA is cleared because seeded rows collide with fixtures.
SETUP_TEST_DATA=
coverage run -m manage test --settings=app.settings_test --testrunner="testrunner.Runner" $1 
cat testresults.txt 
coverage html
coverage json
