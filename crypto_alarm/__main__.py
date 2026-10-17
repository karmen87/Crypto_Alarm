"""Entry point: `python -m crypto_alarm`."""

from __future__ import annotations

import logging
import signal
from types import FrameType

from .settings import Settings
from .web import Services, create_app

log = logging.getLogger("crypto_alarm")


def _terminate(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)  # unwinds socketio.run() so the monitor stops and saves


def main() -> None:
    settings = Settings.from_env()
    app = create_app(settings)
    services: Services = app.extensions["crypto_alarm"]

    signal.signal(signal.SIGTERM, _terminate)
    log.info("Crypto Price Alarm (Binance) on http://%s:%d", settings.host, settings.port)
    log.info(
        "Server-side notifications: %s",
        ", ".join(services.notifier.channels) or "none configured (browser only)",
    )

    try:
        services.socketio.run(
            app, host=settings.host, port=settings.port, debug=False, allow_unsafe_werkzeug=True
        )
    finally:
        services.monitor.stop()


if __name__ == "__main__":
    main()
