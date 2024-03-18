.PHONY: build run clean test

GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD)
GIT_COMMIT := $(shell git rev-parse HEAD)
GIT_COMMIT_TAG := $(shell git describe --tags)

build:
	docker-compose build --build-arg BRANCH=$(GIT_BRANCH) --build-arg COMMIT=$(GIT_COMMIT) --build-arg COMMIT_TAG=$(GIT_COMMIT_TAG)

run: build
	docker-compose up

clean:
	docker-compose down

test:
	coverage run -m pytest
	coverage report
	coverage xml
