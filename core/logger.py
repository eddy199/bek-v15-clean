# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


class JsonLogFormatter(logging.Formatter):
    """Formatter produisant des logs JSON structures conformes aux standards d'observabilite."""

    DEFAULT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
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

        request_id = getattr(record, "request_id", None) or os.getenv("REQUEST_ID")
        if request_id:
            log_record["request_id"] = request_id

        safe_record = {k: self._serialize(v) for k, v in log_record.items()}
        return json.dumps(safe_record, ensure_ascii=False)


def setup_json_logging(
    level: int = logging.INFO,
    stream: Optional[Any] = sys.stdout,
    logger_names: Optional[list[str]] = None,
) -> None:
    """Initialise le handler JSON sans ecraser les handlers existants."""
    json_handler = logging.StreamHandler(stream)
    json_handler.setFormatter(JsonLogFormatter())
    json_handler.setLevel(level)

    if not logger_names:
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(json_handler)
        return

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(json_handler)