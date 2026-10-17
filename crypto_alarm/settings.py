"""All runtime configuration, read once from the environment (see .env.example)."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Web server
    host: str = "127.0.0.1"
    port: int = 5000
    secret_key: str = field(default_factory=lambda: secrets.token_hex(32), repr=False)
    allowed_origins: tuple[str, ...] = ()
    log_json: bool = False

    # Storage: anchored to the project, not the working directory
    data_file: Path = PROJECT_ROOT / "data" / "crypto_data_binance.json"

    # Binance (BINANCE_API_BASE=https://data-api.binance.vision for the market-data-only host)
    binance_api_base: str = "https://api.binance.com"
    binance_ws_base: str = "wss://stream.binance.com:9443"

    # Notification channels (all optional)
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    telegram_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = None
    webhook_url: str | None = field(default=None, repr=False)

    # Tuning
    history_retention: int = 8 * 86400  # seconds; must exceed rules.MAX_WINDOW_SECONDS
    history_spacing: int = 30  # seconds between stored history samples
    cooldown: int = 60  # seconds a restarted target alarm stays disarmed
    max_price_age: int = 120  # alarms ignore prices older than this; the UI marks them stale
    emit_interval: float = 2.0  # seconds between price_update pushes
    save_interval: float = 30.0  # seconds between saves of non-critical changes (max/min)
    notify_min_interval: float = 30.0  # per-alarm minimum seconds between notifications

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        defaults = cls()

        try:
            port = int(env.get("CRYPTO_ALARM_PORT", defaults.port))
        except ValueError:
            raise ValueError("CRYPTO_ALARM_PORT must be an integer") from None

        origins = tuple(
            o.strip() for o in env.get("CRYPTO_ALARM_ALLOWED_ORIGINS", "").split(",") if o.strip()
        )
        data_file = env.get("CRYPTO_ALARM_DATA")

        return cls(
            host=env.get("CRYPTO_ALARM_HOST", defaults.host),
            port=port,
            secret_key=env.get("CRYPTO_ALARM_SECRET_KEY") or defaults.secret_key,
            allowed_origins=origins,
            log_json=_flag(env.get("CRYPTO_ALARM_LOG_JSON")),
            data_file=Path(data_file).expanduser().resolve() if data_file else defaults.data_file,
            binance_api_base=env.get("BINANCE_API_BASE", defaults.binance_api_base),
            binance_ws_base=env.get("BINANCE_WS_BASE", defaults.binance_ws_base),
            ntfy_topic=env.get("NTFY_TOPIC") or None,
            ntfy_server=env.get("NTFY_SERVER", defaults.ntfy_server).rstrip("/"),
            telegram_token=env.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=env.get("TELEGRAM_CHAT_ID") or None,
            webhook_url=env.get("ALARM_WEBHOOK_URL") or None,
        )
