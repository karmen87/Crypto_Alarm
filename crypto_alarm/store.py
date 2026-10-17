"""JSON persistence for pairs and alarms."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from .models import Alarm, Asset

log = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def load(self) -> tuple[dict[str, Asset], dict[str, Alarm]]:
        if not self.path.exists():
            return {}, {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            backup = self.path.with_name(self.path.name + ".corrupt")
            log.exception(
                "Could not read %s; keeping a copy at %s and starting empty", self.path, backup
            )
            try:
                os.replace(self.path, backup)
            except OSError:
                log.exception("Could not move the unreadable data file aside")
            return {}, {}

        assets: dict[str, Asset] = {}
        for ticker, raw in data.get("assets", {}).items():
            try:
                assets[ticker] = Asset.from_dict(raw)
            except (TypeError, ValueError):
                log.warning("Skipping unreadable pair %s in %s", ticker, self.path)

        alarms: dict[str, Alarm] = {}
        for alarm_id, raw in data.get("alarms", {}).items():
            try:
                alarms[alarm_id] = Alarm.from_dict(raw)
            except (TypeError, ValueError):
                log.warning("Skipping unreadable alarm %s in %s", alarm_id, self.path)

        log.info("Loaded %d pairs and %d alarms", len(assets), len(alarms))
        return assets, alarms

    def save(self, payload: dict[str, Any]) -> bool:
        """Atomic write: a crash mid-save can never leave a truncated data file."""
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            return True
        except OSError:
            log.exception("Error saving data to %s", self.path)
            return False
