"""
Server-side alarm notifications, so alarms still reach you when no browser tab is open.

Channels are enabled through settings / environment variables:
  NTFY_TOPIC [+ NTFY_SERVER]                ntfy push
  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID     Telegram bot message
  ALARM_WEBHOOK_URL                         JSON POST {"title", "message"}
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import requests

from .settings import Settings

log = logging.getLogger(__name__)

TITLE = "Crypto Alarm"
ATTEMPTS = 3

Post = Callable[[str], requests.Response]


class Notifier:
    def __init__(self, settings: Settings) -> None:
        self.min_interval = settings.notify_min_interval
        self.channels: dict[str, Post] = {}
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

        if settings.ntfy_topic:
            url = f"{settings.ntfy_server}/{settings.ntfy_topic}"
            self.channels["ntfy"] = lambda msg: requests.post(
                url, data=msg.encode("utf-8"), headers={"Title": TITLE}, timeout=10
            )

        if settings.telegram_token and settings.telegram_chat_id:
            url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
            chat_id = settings.telegram_chat_id
            self.channels["telegram"] = lambda msg: requests.post(
                url, json={"chat_id": chat_id, "text": msg}, timeout=10
            )

        if settings.webhook_url:
            webhook = settings.webhook_url
            self.channels["webhook"] = lambda msg: requests.post(
                webhook, json={"title": TITLE, "message": msg}, timeout=10
            )

    @property
    def enabled(self) -> bool:
        return bool(self.channels)

    def send(self, message: str, key: str | None = None) -> bool:
        """
        Fire-and-forget delivery on every channel. Calls with the same `key` (an alarm id)
        closer together than the minimum interval are dropped, so a flapping alarm can't
        flood a chat. Returns whether the message was dispatched.
        """
        if not self.channels:
            return False

        now = time.monotonic()
        if key is not None:
            with self._lock:
                last = self._last_sent.get(key)
                if last is not None and now - last < self.min_interval:
                    log.info("Suppressed repeat notification for %s", key)
                    return False
                self._last_sent[key] = now

        for name, post in self.channels.items():
            threading.Thread(
                target=self._deliver, args=(name, post, message), name=f"notify-{name}", daemon=True
            ).start()
        return True

    def _deliver(self, name: str, post: Post, message: str) -> None:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                post(message).raise_for_status()
                return
            except Exception as e:
                # Log the type only: request errors embed the URL, which holds the bot token.
                log.warning(
                    "Notification via %s failed (attempt %d/%d): %s",
                    name,
                    attempt,
                    ATTEMPTS,
                    type(e).__name__,
                )
                time.sleep(2 * attempt)
