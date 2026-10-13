import configparser
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dockerfile():
    return (ROOT / "Dockerfile").read_text()


def test_plexapi_config_path_is_copied_into_image():
    text = _dockerfile()
    env = re.search(r"PLEXAPI_CONFIG_PATH=['\"]?([^'\"\s]+)", text)
    assert env, "PLEXAPI_CONFIG_PATH is not set in the Dockerfile"
    path = env.group(1)
    copies = re.findall(r"^COPY\s+(?:--\S+\s+)*(\S+)\s+(\S+)\s*$", text, re.M)
    assert (".plexapi/config.ini", path) in [(s.removeprefix("./"), d) for s, d in copies], (
        f"{path} is not copied into the image"
    )


def test_plexapi_reads_timeout_from_repo_config(monkeypatch):
    cfg = ROOT / ".plexapi" / "config.ini"
    parser = configparser.ConfigParser()
    parser.read(cfg)
    assert parser.getint("plexapi", "timeout") == 240

    from plexapi.config import PlexConfig

    assert PlexConfig(str(cfg)).get("plexapi.timeout", cast=int) == 240
