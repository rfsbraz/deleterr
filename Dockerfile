# syntax=docker/dockerfile:1
# Use an official Python runtime as a parent image
FROM python:3.12-alpine

LABEL maintainer="rfsbraz"

ARG BRANCH
ARG COMMIT
ARG COMMIT_TAG
# The image workflow passes VERSION; COMMIT_TAG is kept for local builds.
ARG VERSION
ARG BUILD_DATE

ENV TZ=UTC
ENV PLEXAPI_CONFIG_PATH='/app/.plexapi/config.ini'
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_LINK_MODE=copy

# Set the working directory in the container to /app
WORKDIR /app

# Install dependencies first so this layer is cached across app-code changes
COPY pyproject.toml uv.lock /app/
# uv is mounted only for this step, so it is not part of the final image
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Copy the current directory contents into the container at /app
COPY ./app /app/app
COPY ./scripts /app/scripts
COPY README.md /app/
COPY .plexapi/config.ini /app/.plexapi/config.ini

# Now that the source is present, install deleterr itself
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

RUN \
  echo ${BRANCH} > /app/branch.txt && \
  echo ${COMMIT} > /app/version.txt && \
  echo ${COMMIT_TAG:-${VERSION}} > /app/commit_tag.txt

RUN \
  mkdir /config && \
  mkdir /config/logs && \
  touch /config/DOCKER

COPY ./config/ /config
VOLUME /config

# Run deleterr when the container launches
CMD ["deleterr"]
