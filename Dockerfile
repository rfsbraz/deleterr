# Use an official Python runtime as a parent image
FROM python:alpine

LABEL maintainer="rfsbraz"

ARG BRANCH
ARG COMMIT
ARG COMMIT_TAG

ENV TZ=UTC
ENV PLEXAPI_CONFIG_PATH='/app/.plexapi/config.ini'

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

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

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run deleterr.py when the container launches
CMD ["python", "-m", "app.deleterr"]