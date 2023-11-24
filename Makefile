.PHONY: build run clean test

build:
	docker-compose build

run: build
	docker-compose up

clean:
	docker-compose down

test:
	pytest
