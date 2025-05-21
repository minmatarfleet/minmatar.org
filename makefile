.PHONY: build run stop setup

build:
	docker compose build

run: stop build
	docker compose \
		-f docker-compose.yml \
		up \
		--exit-code-from proxy --abort-on-container-exit \
		proxy

stop:
	docker compose \
	-f docker-compose.yml \
	down

setup:
# todo: setup .env files
