"""Flask + Socket.IO application factory."""

from __future__ import annotations

import atexit
import functools
import logging
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flask import Flask, Response, jsonify, render_template
from flask_socketio import SocketIO, emit

from .binance import BinanceClient
from .logs import configure as configure_logging
from .monitor import Monitor
from .notifier import Notifier
from .settings import Settings
from .store import JsonStore

log = logging.getLogger(__name__)

# Windows can map .js to text/plain in the registry, and browsers refuse to run ES modules
# served that way.
mimetypes.add_type("text/javascript", ".js")

Handler = Callable[[dict[str, Any]], None]


@dataclass
class Services:
    settings: Settings
    socketio: SocketIO
    monitor: Monitor
    notifier: Notifier


def create_app(settings: Settings | None = None, *, start_monitor: bool = True) -> Flask:
    """
    Build the app. Also usable as a WSGI target:
    `gunicorn -k gthread -w 1 --threads 100 'crypto_alarm.web:create_app()'`.
    Run a single worker: pairs, alarms and price history live in this process.
    """
    settings = settings or Settings.from_env()
    configure_logging(settings.log_json)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key

    # Same-origin only unless extra origins are listed explicitly.
    socketio = SocketIO(
        app,
        cors_allowed_origins=list(settings.allowed_origins) or None,
        async_mode="threading",
        ping_timeout=60,
        ping_interval=25,
    )
    notifier = Notifier(settings)
    monitor = Monitor(
        settings,
        BinanceClient(settings.binance_api_base),
        JsonStore(settings.data_file),
        notifier,
        on_update=lambda state: socketio.emit("price_update", state),
        on_trigger=lambda event: socketio.emit("alarm_triggered", event),
    )
    app.extensions["crypto_alarm"] = Services(settings, socketio, monitor, notifier)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/healthz")
    def healthz() -> tuple[Response, int]:
        report = monitor.health()
        return jsonify(report), 503 if report["status"] != "ok" else 200

    def handler(event: str) -> Callable[[Handler], Callable[[Any], None]]:
        """Register a socket event; user-input errors go back to the client, bugs get logged."""

        def decorator(func: Handler) -> Callable[[Any], None]:
            @functools.wraps(func)
            def wrapper(data: Any = None) -> None:
                try:
                    func(data if isinstance(data, dict) else {})
                except ValueError as e:
                    emit("error", {"message": str(e)})
                except Exception:
                    log.exception("Error handling %s", event)
                    emit("error", {"message": "Internal server error"})

            socketio.on(event)(wrapper)
            return wrapper

        return decorator

    def on_connect() -> None:
        emit("initial_state", monitor.get_state())
        for event in monitor.get_pending_events():
            emit("alarm_triggered", event)

    socketio.on("connect")(on_connect)

    @handler("add_asset")
    def add_asset(data: dict[str, Any]) -> None:
        emit("asset_added", {"asset": monitor.add_asset(data.get("pair"))}, broadcast=True)

    @handler("remove_asset")
    def remove_asset(data: dict[str, Any]) -> None:
        monitor.remove_asset(data.get("ticker"))
        emit("asset_removed", {"ticker": data.get("ticker")}, broadcast=True)

    @handler("reset_extremes")
    def reset_extremes(data: dict[str, Any]) -> None:
        monitor.reset_extremes(data.get("ticker"))
        emit("price_update", monitor.get_state(), broadcast=True)

    @handler("add_alarm")
    def add_alarm(data: dict[str, Any]) -> None:
        kind, ticker = data.get("type"), str(data.get("ticker"))
        if kind == "target":
            alarm = monitor.add_target_alarm(ticker, data.get("targetPrice"), data.get("direction"))
        elif kind == "extreme":
            alarm = monitor.add_extreme_alarm(
                ticker, data.get("percentage"), data.get("extremeType")
            )
        elif kind == "timeframe":
            alarm = monitor.add_timeframe_alarm(
                ticker,
                data.get("percentage"),
                data.get("direction"),
                data.get("timeValue"),
                data.get("timeUnit"),
            )
        else:
            raise ValueError("Invalid alarm type")
        emit("alarm_added", {"alarm": alarm}, broadcast=True)

    @handler("remove_alarm")
    def remove_alarm(data: dict[str, Any]) -> None:
        monitor.remove_alarm(data.get("alarmId"))
        emit("alarm_removed", {"alarmId": data.get("alarmId")}, broadcast=True)

    @handler("restart_alarm")
    def restart_alarm(data: dict[str, Any]) -> None:
        monitor.restart_alarm(data.get("alarmId"))
        emit("alarm_restarted", {"alarmId": data.get("alarmId")}, broadcast=True)

    @handler("ack_alarm")
    def ack_alarm(data: dict[str, Any]) -> None:
        monitor.acknowledge_alarm(data.get("alarmId"))

    if start_monitor:
        monitor.start()
        atexit.register(monitor.stop)

    return app
