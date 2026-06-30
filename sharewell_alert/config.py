from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean value, got {value!r}")


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be greater than 0")
    return parsed


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return parsed


@dataclass(frozen=True)
class Config:
    api_url: str
    site_url: str
    slack_webhook_url: str | None
    slack_bot_token: str | None
    slack_channel_id: str | None
    slack_thread_details: bool
    interval_seconds: int
    state_file: Path
    kind: str
    in_stock_only: bool
    expired_also: bool
    limit: int
    request_timeout_seconds: float
    notify_on_first_run: bool
    max_pages: int
    user_agent: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_url=os.getenv(
                "SHAREWEL_API_URL",
                "https://sharewel.riise.u-tokyo.ac.jp/api/v1/exhibits",
            ),
            site_url=os.getenv("SHAREWEL_SITE_URL", "https://sharewel.riise.u-tokyo.ac.jp"),
            slack_webhook_url=_env_optional("SLACK_WEBHOOK_URL"),
            slack_bot_token=_env_optional("SLACK_BOT_TOKEN"),
            slack_channel_id=_env_optional("SLACK_CHANNEL_ID"),
            slack_thread_details=_env_bool("SLACK_THREAD_DETAILS", True),
            interval_seconds=_env_int("SHAREWEL_CHECK_INTERVAL_SECONDS", 60),
            state_file=Path(os.getenv("SHAREWEL_STATE_FILE", ".sharewell_state.json")),
            kind=os.getenv("SHAREWEL_KIND", "reuse"),
            in_stock_only=_env_bool("SHAREWEL_IN_STOCK_ONLY", True),
            expired_also=_env_bool("SHAREWEL_EXPIRED_ALSO", False),
            limit=_env_int("SHAREWEL_LIMIT", 150),
            request_timeout_seconds=_env_float("SHAREWEL_REQUEST_TIMEOUT_SECONDS", 15.0),
            notify_on_first_run=_env_bool("SHAREWEL_NOTIFY_ON_FIRST_RUN", False),
            max_pages=_env_int("SHAREWEL_MAX_PAGES", 20),
            user_agent=os.getenv("SHAREWEL_USER_AGENT", "sharewell-alert/0.1"),
        )

    def with_overrides(
        self,
        *,
        interval_seconds: int | None = None,
        state_file: Path | None = None,
        notify_on_first_run: bool | None = None,
    ) -> "Config":
        return Config(
            api_url=self.api_url,
            site_url=self.site_url,
            slack_webhook_url=self.slack_webhook_url,
            slack_bot_token=self.slack_bot_token,
            slack_channel_id=self.slack_channel_id,
            slack_thread_details=self.slack_thread_details,
            interval_seconds=interval_seconds or self.interval_seconds,
            state_file=state_file or self.state_file,
            kind=self.kind,
            in_stock_only=self.in_stock_only,
            expired_also=self.expired_also,
            limit=self.limit,
            request_timeout_seconds=self.request_timeout_seconds,
            notify_on_first_run=(
                self.notify_on_first_run
                if notify_on_first_run is None
                else notify_on_first_run
            ),
            max_pages=self.max_pages,
            user_agent=self.user_agent,
        )
