# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Logger JSON structuré
# ==============================================================================
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


class JsonLogFormatter(logging.Formatter):
    """Formatter produisant des logs JSON structurés."""

    DEFAULT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def formatTime(
        self,
        record: logging.LogRecord,
        datefmt: Optional[str] = None,
    ) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(self.DEFAULT_TIME_FORMAT)

    def formatException(self, exc_info) -> str:
        return super().formatException(exc_info)

    def _serialize(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def format(self, record: logging.LogRecord) -> str:
        log_record: Mapping[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        request_id = (
            getattr(record, "request_id", None) or os.getenv("REQUEST_ID")
        )
        if request_id:
            log_record["request_id"] = request_id

        safe_record = {
            key: self._serialize(value)
            for key, value in log_record.items()
        }

        return json.dumps(
            safe_record,
            ensure_ascii=False,
        )


def _has_json_handler(logger: logging.Logger) -> bool:
    """Vérifie si le logger possède déjà notre handler JSON."""
    return any(
        isinstance(handler, logging.StreamHandler)
        and isinstance(handler.formatter, JsonLogFormatter)
        for handler in logger.handlers
    )


def setup_json_logging(
    level: int = logging.INFO,
    stream: Optional[Any] = sys.stdout,
    logger_names: Optional[list[str]] = None,
) -> None:
    """
    Initialise les logs JSON sans dupliquer les handlers.

    Si logger_names est None, configure le logger racine.
    Sinon, configure uniquement les loggers demandés.
    """
    if logger_names:
        target_loggers = [
            logging.getLogger(name) for name in logger_names
        ]
    else:
        target_loggers = [logging.getLogger()]

    for logger in target_loggers:
        logger.setLevel(level)

        if _has_json_handler(logger):
            continue

        json_handler = logging.StreamHandler(stream)
        json_handler.setFormatter(JsonLogFormatter())
        json_handler.setLevel(level)
        logger.addHandler(json_handler)