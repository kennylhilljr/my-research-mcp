"""Validated configuration. Loading and directory creation are explicit startup work."""

from datetime import date
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

PositiveInt = Annotated[int, Field(gt=0)]
ClockTime = Annotated[str, Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")]


class Section(BaseModel):
    # Schema construction can read plugin settings; defer it until startup.
    model_config = ConfigDict(
        extra="forbid", validate_default=True, hide_input_in_errors=True, defer_build=True
    )


class ServerSettings(Section):
    host: str = "127.0.0.1"
    port: int = Field(default=7319, ge=1, le=65535)
    token: str = Field(default="keychain:research-mcp/DAEMON_TOKEN")

    @field_validator("host")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        try:
            loopback = ip_address(value).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise ValueError("server.host must be a loopback IP address")
        return value

    @field_validator("token")
    @classmethod
    def reference_only(cls, value: str) -> str:
        prefixes = ("keychain:research-mcp/", "env:")
        if not any(
            value.startswith(prefix) and value[len(prefix) :].strip() for prefix in prefixes
        ):
            raise ValueError("server.token must be a Keychain or environment reference")
        return value


class PathSettings(Section):
    state_dir: Path = Path("~/Library/Application Support/research-mcp")
    data_dir: Path = Path("~/Library/Application Support/research-mcp/cache")
    model_cache_dir: Path = Path("~/Library/Caches/research-mcp/models")
    log_dir: Path = Path("~/Library/Logs/research-mcp")

    @field_validator("*")
    @classmethod
    def absolute_path(cls, value: Path) -> Path:
        value = value.expanduser()
        if not value.is_absolute():
            raise ValueError("directory paths must be absolute")
        return value

    def create_directories(self) -> None:
        """Create private runtime directories at daemon start, not during loading."""
        directories = (
            self.state_dir,
            self.data_dir,
            self.model_cache_dir,
            self.log_dir,
            self.state_dir / "backups",
            self.state_dir / "imports",
            self.data_dir / "files",
            self.data_dir / "trash",
            self.data_dir / "tmp",
        )
        for directory in directories:
            _private_directory(directory)


def _private_directory(path: Path) -> None:
    """Give newly created intermediate directories the same private mode."""
    if not path.parent.exists():
        _private_directory(path.parent)
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)


class ContactSettings(Section):
    email: str | None = None

    @field_validator("email")
    @classmethod
    def real_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        local, separator, domain = value.rpartition("@")
        domain = domain.lower().rstrip(".")
        if (
            not separator
            or not local
            or "@" in local
            or "." not in domain
            or any(character.isspace() for character in value)
        ):
            raise ValueError("contact.email must be a valid email address")
        if any(
            domain == blocked or domain.endswith("." + blocked)
            for blocked in ("example.com", "example.org", "test", "invalid")
        ):
            raise ValueError("contact.email must not use a placeholder domain")
        return value


class LimitSettings(Section):
    response_bytes: PositiveInt = 65536
    download_bytes: PositiveInt = 52428800
    pdf_pages: PositiveInt = 500
    chunk_hard_cap_chars: PositiveInt = 4000


class FederationSettings(Section):
    deadline_s: float = Field(default=8.0, gt=0, allow_inf_nan=False)
    default_groups: list[str] = Field(default_factory=lambda: ["scholarly", "preprints"])


class CacheSettings(Section):
    retention_days: PositiveInt = 120
    review_lead_days: int = Field(default=3, ge=0)
    review_time_local: ClockTime = "09:00"
    batch_open_hours: PositiveInt = 24
    reask_days: PositiveInt = 7
    trash_days: PositiveInt = 7


class ArchiveSettings(Section):
    target: str = "auto"
    confirmed_path: Path | None = None
    subfolder: str = "Research Archive/{year}"
    fallback: str = "~/Research Archive/{year}"

    @field_validator("target")
    @classmethod
    def absolute_target(cls, value: str) -> str:
        if value != "auto" and not Path(value).is_absolute():
            raise ValueError("archive.target must be auto or an absolute path")
        return value

    @field_validator("confirmed_path")
    @classmethod
    def absolute_confirmation(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("archive.confirmed_path must be absolute")
        return value


class NotifySettings(Section):
    macos: bool = True
    webhook_url: HttpUrl | None = None
    quiet_hours: str = Field(
        default="21:00-08:00",
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d$",
    )

    @field_validator("webhook_url")
    @classmethod
    def no_url_credentials(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and (
            value.username or value.password or value.query or value.fragment
        ):
            raise ValueError("notify.webhook_url must not contain credentials, query or fragment")
        return value


class DiskSettings(Section):
    cache_warn_bytes: PositiveInt = 5368709120
    free_warn_bytes: PositiveInt = 16106127360
    free_crit_bytes: PositiveInt = 5368709120


class BackupSettings(Section):
    keep: PositiveInt = 7


class SourceSettings(Section):
    # Adapter-specific fields are validated by each SourceSpec during registry setup.
    model_config = ConfigDict(extra="allow")
    enabled: bool | None = None
    budget_cap: int | None = Field(default=None, ge=0)


class CredentialSettings(Section):
    rotate_by: date | None = None


class Settings(BaseSettings):
    """Load TOML and nested environment overrides when explicitly instantiated."""

    model_config = SettingsConfigDict(
        env_prefix="RESEARCH_MCP_",
        env_nested_delimiter="__",
        extra="forbid",
        hide_input_in_errors=True,
        defer_build=True,
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    contact: ContactSettings = Field(default_factory=ContactSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    federation: FederationSettings = Field(default_factory=FederationSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    archive: ArchiveSettings = Field(default_factory=ArchiveSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    disk: DiskSettings = Field(default_factory=DiskSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    sources: dict[str, SourceSettings] = Field(default_factory=dict)
    credentials: dict[str, CredentialSettings] = Field(default_factory=dict)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(
                settings_cls, toml_file=Path.home() / ".config/research-mcp/config.toml"
            ),
        )

    def create_directories(self) -> None:
        """Explicit synchronous startup hook for the daemon or installer."""
        self.paths.create_directories()
