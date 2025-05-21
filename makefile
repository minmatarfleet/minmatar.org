.PHONY: build build-tests run stop setup test front-end-unit-tests

build: build-tests
	docker compose \
		-f docker-compose.yml \
		build

build-tests:
	docker compose \
		-f docker-compose.ci.yml \
		build

run: stop build
	docker compose \
		-f docker-compose.yml \
		up \
		--exit-code-from proxy --abort-on-container-exit \
		proxy

stop:
	docker compose \
		-f docker-compose.yml \
		-f docker-compose.ci.yml \
		down

stop-test:
	docker compose \
		-f docker-compose.ci.yml \
		down

test: front-end-unit-tests

front-end-unit-tests: stop-test build-tests
	docker compose \
		-f docker-compose.ci.yml \
		up \
		--exit-code-from frontend-unit-tests --abort-on-container-exit \
		frontend-unit-tests

setup:
# todo: setup .env files
