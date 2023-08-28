# Deleterr

Deleterr uses Radarr, Sonarr, and Tautulli to identify and delete media files based on user-specified criteria. Deleterr is customizable, allowing you to specify metadata based rules for different libraries and sonarr/radarr instances.

Setup Deleterr to run on a schedule and it will automatically delete media files that meet your criteria. This allows to keep your library fresh and clean, without having to manually manage it to free up space.

## WARNING

* **DO NOT USE THIS WITH MEDIA CONTENT YOU CAN'T AFFORD TO LOSE**
* Turn on the recycle bin in your Sonarr/Radarr settings if you want to be able to recover deleted files (not recommended for remote mounts)

### Docker Compose

Adding deleterr to your docker-compose file is really easy and can be combined with ofelia to run at a schedule. Here's an example that runs deleterr weekly:

```yaml
version: "3.9"
services:
    deleterr:
        image: ghcr.io/rfsbraz/deleterr:master
        container_name: deleterr
        environment:
            LOG_LEVEL: DEBUG
        volumes:
            - ./config:/config
            - ./logs:/config/logs
        restart: on-failure:2
    scheduler:
        image: mcuadros/ofelia:latest
        container_name: scheduler
        depends_on:
            - deleterr
        command: daemon --docker
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        labels:
            ofelia.job-run.deleterr.schedule: "@weekly"
            ofelia.job-run.deleterr.container: "deleterr"
```

You can find more information about ofelia's scheduling options [here](https://github.com/mcuadros/ofelia#jobs).

### Docker

Set your settings file in `config/settings.yaml` and run the following command:

```bash
docker run -v ./config:/config -v ./logs:/config/logs ghcr.io/rfsbraz/deleterr:master -e LOG_LEVEL=DEBUG
```

## Configuration

Deleterr is configured via a YAML file. An example configuration file, `settings.example.yaml`, is provided. Copy this file to `settings.yaml` and adjust the settings as needed.

Please refer to the [configuration guide](./docs/CONFIGURATION.md) for a full list of options and their descriptions.
