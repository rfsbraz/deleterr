.PHONY: build run clean test

GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD)
GIT_COMMIT := $(shell git rev-parse HEAD)
GIT_COMMIT_TAG := $(shell git describe --tags)

BUILD_DATE := $(shell date +'%Y-%m-%dT%H:%M:%S')

build:
	docker-compose build --build-arg BRANCH=$(GIT_BRANCH) --build-arg COMMIT=$(GIT_COMMIT) --build-arg COMMIT_TAG=$(GIT_COMMIT_TAG) --build-arg BUILD_DATE=$(BUILD_DATE)

run: build
	docker-compose up

clean:
	docker-compose down

test:
	uv run coverage run -m pytest
	uv run coverage report
	uv run coverage xml

unit:
	uv run coverage run -m pytest -m "not integration and not slow"
	uv run coverage report
	uv run coverage xml

integration:
	uv run coverage run -m pytest -m integration
	uv run coverage report
	uv run coverage xml