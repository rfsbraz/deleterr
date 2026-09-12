# Use an official Python runtime as a parent image
FROM python:3.12-alpine

LABEL maintainer="rfsbraz"

ARG BRANCH
ARG COMMIT
ARG COMMIT_TAG
ARG BUILD_DATE

ENV TZ=UTC
ENV PLEXAPI_CONFIG_PATH='/app/.plexapi/config.ini'
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory in the container to /app
WORKDIR /app

# Install dependencies first so this layer is cached across app-code changes
COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-dev

# Copy the current directory contents into the container at /app
COPY ./app /app/app
COPY ./scripts /app/scripts

RUN \
  echo ${BRANCH} > /app/branch.txt && \
  echo ${COMMIT} > /app/version.txt && \
  echo ${COMMIT_TAG} > /app/commit_tag.txt

RUN \
  mkdir /config && \
  mkdir /config/logs && \
  touch /config/DOCKER

COPY ./config/ /config
VOLUME /config

# Run deleterr.py when the container launches
CMD ["python", "-m", "app.deleterr"]
