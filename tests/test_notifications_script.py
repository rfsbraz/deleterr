from types import SimpleNamespace

import pytest

from scripts import test_notifications


def test_status_uses_default_config_path_and_settings(monkeypatch):
    fake_config = SimpleNamespace(settings={"notifications": {"email": {"enabled": True}}})
    seen: dict[str, object] = {}

    def fake_load_config(path):
        seen["path"] = path
        return fake_config

    def fake_show_config_status(config):
        seen["status_config"] = config

    monkeypatch.setattr(test_notifications, "load_config", fake_load_config)
    monkeypatch.setattr(test_notifications, "show_config_status", fake_show_config_status)
    monkeypatch.setattr(
        test_notifications.sys,
        "argv",
        ["test_notifications.py", "--status"],
    )

    with pytest.raises(SystemExit) as exc:
        test_notifications.main()

    assert exc.value.code == 0
    assert seen["path"] == "/config/settings.yaml"
    assert seen["status_config"] == fake_config.settings


def test_run_summary_uses_config_object_for_notification_manager(monkeypatch):
    fake_config = SimpleNamespace(settings={"notifications": {"enabled": True}})
    seen: dict[str, object] = {}

    def fake_load_config(path):
        seen["path"] = path
        return fake_config

    def fake_show_config_status(config):
        seen["status_config"] = config

    class FakeNotificationManager:
        def __init__(self, config):
            seen["manager_config"] = config

    def fake_test_run_summary(manager, provider_filter=None, dry_run=False):
        seen["run_summary_args"] = (manager, provider_filter, dry_run)
        return True

    monkeypatch.setattr(test_notifications, "load_config", fake_load_config)
    monkeypatch.setattr(test_notifications, "show_config_status", fake_show_config_status)
    monkeypatch.setattr(test_notifications, "NotificationManager", FakeNotificationManager)
    monkeypatch.setattr(test_notifications, "test_run_summary", fake_test_run_summary)
    monkeypatch.setattr(
        test_notifications.sys,
        "argv",
        ["test_notifications.py", "--type", "run_summary", "--dry-run"],
    )

    with pytest.raises(SystemExit) as exc:
        test_notifications.main()

    assert exc.value.code == 0
    assert seen["path"] == "/config/settings.yaml"
    assert seen["status_config"] == fake_config.settings
    assert seen["manager_config"] is fake_config
    assert seen["run_summary_args"][1:] == (None, True)


def test_test_run_summary_uses_current_manager_api():
    class FakeManager:
        def is_enabled(self):
            return True

        def send_run_summary(self, result):
            return True

    assert test_notifications.test_run_summary(FakeManager(), dry_run=False) is True


def test_test_leaving_soon_passes_seerr_url():
    captured: dict[str, object] = {}

    class FakeManager:
        def is_leaving_soon_enabled(self):
            return True

        def send_leaving_soon(self, **kwargs):
            captured.update(kwargs)
            return True

    config = {
        "plex": {"url": "https://plex.example.com"},
        "seerr": {"url": "https://seerr.example.com"},
    }

    assert test_notifications.test_leaving_soon(FakeManager(), config) is True
    assert captured["plex_url"] == "https://plex.example.com"
    assert captured["seerr_url"] == "https://seerr.example.com"


def test_filter_providers_limits_run_summary_manager():
    email_provider = SimpleNamespace(name="email")
    discord_provider = SimpleNamespace(name="discord")
    manager = SimpleNamespace(providers=[email_provider, discord_provider])

    assert test_notifications.filter_providers(manager, "email") is True
    assert manager.providers == [email_provider]


def test_filter_providers_rejects_missing_provider():
    manager = SimpleNamespace(providers=[SimpleNamespace(name="discord")])

    assert test_notifications.filter_providers(manager, "email") is False
    assert manager.providers == []
