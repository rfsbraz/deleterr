# Deleterr

Disk space is finite, but so is your time. Automate removing inactive media with Deleterr.

## WARNING

DO NOT USE THIS WITH MEDIA CONTENT YOU CAN'T AFFORD TO LOSE

## Overview

Deleterr is a Python script designed to help you manage your Plex media server. It uses Radarr, Sonarr, and Tautulli to identify and delete media files based on user-specified criteria. Deleterr is customizable, allowing you to specify rules for different libraries, as well as tags, collections, and genres to exclude.

## Installation

### Docker (Recommended)

1. Clone the repository: `git clone https://github.com/rfsbraz/Deleterr.git`
2. Enter the cloned directory: `cd Deleterr`
3. Build the Docker image: `docker build -t deleterr .`
4. Run the Docker container: `docker run deleterr`

### Pre-Built Image from Docker Hub

TODO

## Configuration

Deleterr is configured via a YAML file. An example configuration file, `settings.example.yaml`, is provided. Copy this file to `settings.yaml` and adjust the settings as needed.

Please refer to the [example configuration file](./config/settings.example.yaml) for a full list of options and their descriptions.

## Usage

To start Deleterr, simply run `python deleterr.py`. You can also set it to run on a schedule using a cron job or a similar scheduling tool.

## Thanks

https://github.com/nwithan8/pytulli

https://github.com/pkkid/python-plexapi

https://github.com/totaldebug/pyarr

https://github.com/fuzeman/trakt.py

https://github.com/Tautulli/Tautulli