import yaml
import logger
import sys

class Config:
    def __init__(self, config_file):
        try:
            with open(config_file, 'r') as stream:
                try:
                    self.config = yaml.safe_load(stream)
                except yaml.YAMLError as exc:
                    print(exc)
        except FileNotFoundError:
            logger.error(f"Configuration file {config_file} not found. Copy the example config and edit it to your needs.")
            sys.exit(1)

    def get(self, *keys, default=None):
        """
        Traverse the configuration dictionary with the given keys. If any key is not found,
        return the default value. If no default is provided, None is returned.
        """
        config = self.config
        try:
            for key in keys:
                config = config[key]
            return config
        except KeyError:
            return default
