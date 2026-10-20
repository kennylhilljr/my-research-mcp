"""Offline acceptance coverage for settings and startup paths."""

# These assertions and rejected wildcard addresses are test inputs.
# ruff: noqa: S101, S104

import os
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_mcp.settings import Settings


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a temporary home and prevent all external network access."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in tuple(os.environ):
        if key.startswith("RESEARCH_MCP_"):
            monkeypatch.delenv(key)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("settings must not use the network")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)


def test_defaults(tmp_path: Path) -> None:
    """AT-PLAT-08: Every fixed LLD section 2 default is represented."""
    settings = Settings()
    values = settings.model_dump(exclude={"paths"})
    assert values == {
        "server": {
            "host": "127.0.0.1",
            "port": 7319,
            "token": "keychain:research-mcp/DAEMON_TOKEN",
        },
        "contact": {"email": None},
        "limits": {
            "response_bytes": 65536,
            "download_bytes": 52428800,
            "pdf_pages": 500,
            "chunk_hard_cap_chars": 4000,
        },
        "federation": {"deadline_s": 8.0, "default_groups": ["scholarly", "preprints"]},
        "cache": {
            "retention_days": 120,
            "review_lead_days": 3,
            "review_time_local": "09:00",
            "batch_open_hours": 24,
            "reask_days": 7,
            "trash_days": 7,
        },
        "archive": {
            "target": "auto",
            "confirmed_path": None,
            "subfolder": "Research Archive/{year}",
            "fallback": "~/Research Archive/{year}",
        },
        "notify": {"macos": True, "webhook_url": None, "quiet_hours": "21:00-08:00"},
        "disk": {
            "cache_warn_bytes": 5368709120,
            "free_warn_bytes": 16106127360,
            "free_crit_bytes": 5368709120,
        },
        "backup": {"keep": 7},
        "sources": {},
        "credentials": {},
    }
    assert list(tmp_path.iterdir()) == []


def test_toml_and_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-08: Nested environment values override TOML without losing siblings."""
    config = tmp_path / ".config/research-mcp/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "[server]\nport = 7400\n"
        "[cache]\nretention_days = 60\nreask_days = 10\n"
        '[sources.dspace_penn]\nenabled = false\nbase_url = "https://repository.upenn.edu"\n'
        '[credentials.CORE_API_KEY]\nrotate_by = "2027-01-01"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("RESEARCH_MCP_CACHE__RETENTION_DAYS", "150")
    monkeypatch.setenv("RESEARCH_MCP_SOURCES__DSPACE_PENN__ENABLED", "true")
    monkeypatch.setenv("RESEARCH_MCP_FEDERATION__DEFAULT_GROUPS", '["preprints"]')
    settings = Settings()
    assert settings.server.port == 7400
    assert settings.cache.retention_days == 150
    assert settings.cache.reask_days == 10
    assert settings.federation.default_groups == ["preprints"]
    assert settings.sources["dspace_penn"].enabled is True
    assert settings.sources["dspace_penn"].model_extra == {
        "base_url": "https://repository.upenn.edu"
    }
    assert str(settings.credentials["CORE_API_KEY"].rotate_by) == "2027-01-01"


@pytest.mark.parametrize(
    ("key", "value", "location"),
    [
        ("SERVER__PORT", "0", "server.port"),
        ("SERVER__PORT", "65536", "server.port"),
        ("CACHE__RETENTION_DAYS", "-1", "cache.retention_days"),
        ("CACHE__REVIEW_TIME_LOCAL", "25:00", "cache.review_time_local"),
        ("LIMITS__PDF_PAGES", "many", "limits.pdf_pages"),
        ("FEDERATION__DEADLINE_S", "nan", "federation.deadline_s"),
        ("BACKUP__KEEP", "0", "backup.keep"),
        ("PATHS__DATA_DIR", "relative", "paths.data_dir"),
        ("ARCHIVE__TARGET", "relative", "archive.target"),
        ("ARCHIVE__CONFIRMED_PATH", "relative", "archive.confirmed_path"),
        ("NOTIFY__QUIET_HOURS", "25:00-08:00", "notify.quiet_hours"),
        (
            "NOTIFY__WEBHOOK_URL",
            "https://localhost/?token=fixture",
            "notify.webhook_url",
        ),
        ("SERVER__TOKEN", "fixture-raw-value", "server.token"),
    ],
)
def test_invalid_environment(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str, location: str
) -> None:
    """AT-PLAT-08: Invalid overrides report the offending setting."""
    monkeypatch.setenv("RESEARCH_MCP_" + key, value)
    with pytest.raises(ValidationError, match=location):
        Settings()


def test_invalid_toml(tmp_path: Path) -> None:
    """AT-PLAT-08: Unknown TOML settings fail instead of silently using defaults."""
    config = tmp_path / ".config/research-mcp/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text("[cache]\nretenton_days = 60\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="cache.retenton_days"):
        Settings()


def test_paths_and_private_creation(tmp_path: Path) -> None:
    """AT-PLAT-09: Durable data and disposable models use separate private roots."""
    settings = Settings()
    support = tmp_path / "Library/Application Support/research-mcp"
    assert settings.paths.state_dir == support
    assert settings.paths.data_dir == support / "cache"
    assert settings.paths.model_cache_dir == tmp_path / "Library/Caches/research-mcp/models"
    assert settings.paths.log_dir == tmp_path / "Library/Logs/research-mcp"
    assert not support.exists()
    settings.create_directories()
    settings.paths.log_dir.chmod(0o755)
    settings.create_directories()
    for directory in tmp_path.rglob("*"):
        assert directory.is_dir()
        assert directory.stat().st_mode & 0o777 == 0o700
    for directory in ("backups", "imports", "cache/files", "cache/trash", "cache/tmp"):
        assert (support / directory).is_dir()


def test_path_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-09: Configured paths expand the home without creating directories."""
    monkeypatch.setenv("RESEARCH_MCP_PATHS__DATA_DIR", "~/custom/data")
    settings = Settings()
    assert settings.paths.data_dir == tmp_path / "custom/data"
    assert not settings.paths.data_dir.exists()


def test_existing_parent_permissions(tmp_path: Path) -> None:
    """AT-PLAT-09: Startup preserves permissions on preexisting shared parents."""
    library = tmp_path / "Library"
    library.mkdir(mode=0o755)
    library.chmod(0o755)
    settings = Settings()
    settings.create_directories()
    assert library.stat().st_mode & 0o777 == 0o755
    assert settings.paths.state_dir.stat().st_mode & 0o777 == 0o700
    assert settings.paths.data_dir.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "email",
    [
        "",
        "missing-at",
        "@university.edu",
        "a@@university.edu",
        "a b@university.edu",
        "a@.edu",
        "a@university..edu",
        "a@-university.edu",
        "a@university-.edu",
        "a@university/department.edu",
    ],
)
def test_malformed_contact(email: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-11: Malformed contact values fail with a settings validation error."""
    monkeypatch.setenv("RESEARCH_MCP_CONTACT__EMAIL", email)
    with pytest.raises(ValidationError, match="contact.email"):
        Settings()


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.1", "localhost", "bad-host"])
def test_reject_non_loopback(host: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-10: Non-loopback addresses and unresolved names are rejected."""
    monkeypatch.setenv("RESEARCH_MCP_SERVER__HOST", host)
    with pytest.raises(ValidationError, match="loopback"):
        Settings()


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1"])
def test_accept_loopback(host: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-10: IPv4 and IPv6 loopback literals are accepted without DNS."""
    monkeypatch.setenv("RESEARCH_MCP_SERVER__HOST", host)
    assert Settings().server.host == host


@pytest.mark.parametrize(
    "domain",
    [
        "example.com",
        "EXAMPLE.ORG",
        "sub.example.com",
        "mail.test",
        "mail.invalid",
        "test",
        "invalid",
    ],
)
def test_reject_placeholder_contact(domain: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-11: Reserved placeholder domains cannot be used as contact details."""
    monkeypatch.setenv("RESEARCH_MCP_CONTACT__EMAIL", "owner@" + domain)
    with pytest.raises(ValidationError, match="contact.email"):
        Settings()


def test_optional_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-PLAT-11: An unset contact or a non-placeholder email is allowed offline."""
    assert Settings().contact.email is None
    monkeypatch.setenv("RESEARCH_MCP_CONTACT__EMAIL", "researcher@university.edu")
    assert Settings().contact.email == "researcher@university.edu"


@pytest.mark.parametrize(
    ("section", "setting", "value", "location"),
    [
        ("server", "port", "70000", "server.port"),
        ("server", "host", '"192.168.1.1"', "server.host"),
        ("contact", "email", '"owner@example.com"', "contact.email"),
        ("cache", "retention_days", "0", "cache.retention_days"),
    ],
)
def test_invalid_config_values(
    tmp_path: Path, section: str, setting: str, value: str, location: str
) -> None:
    """AT-PLAT-08: TOML values receive the same validation as environment overrides."""
    config = tmp_path / ".config/research-mcp/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(f"[{section}]\n{setting} = {value}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match=location):
        Settings()
