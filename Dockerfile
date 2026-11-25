# syntax=docker/dockerfile:1
# Pinned uv, only mounted at build time. Dependabot bumps the tag and digest.
FROM ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f AS uv

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
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Copy the current directory contents into the container at /app
COPY ./app /app/app
COPY ./scripts /app/scripts
COPY README.md /app/
COPY .plexapi/config.ini /app/.plexapi/config.ini

# Now that the source is present, install deleterr itself
RUN --mount=from=uv,source=/uv,target=/bin/uv \
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

# The healthcheck script reads /config/.deleterr_last_run.json (stdlib only).
HEALTHCHECK --interval=5m --timeout=10s --start-period=2m --retries=3     CMD python3 /app/scripts/healthcheck.py

# Run deleterr when the container launches
CMD ["deleterr"]
