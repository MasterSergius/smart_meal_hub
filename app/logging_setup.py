"""Logging configuration (spec v0.2.0 OPS-4).

``text`` is the human-readable default for local runs; ``json`` writes one JSON
object per line to stdout, which CloudWatch Logs can parse and filter by field.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Extra fields that request logging attaches via ``logger.info(..., extra={...})``.
REQUEST_FIELDS = ("method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    """Formats a record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Build ``{"time", "level", "logger", "message", ...request fields, "exc_info"?}``."""
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in REQUEST_FIELDS:
            if hasattr(record, name):
                entry[name] = getattr(record, name)
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(log_format: str) -> None:
    """Send the root logger's INFO+ records to stdout in the chosen format.

    Replaces existing root handlers, so calling it twice doesn't duplicate output.
    """
    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
