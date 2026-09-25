"""Small, dependency-free structured logging helpers for operational events."""
import json
import logging


logger = logging.getLogger("forecast_intelligence.operations")


def log_event(event: str, **fields) -> None:
    """Emit only caller-selected, safe fields; never serialize provider payloads."""
    logger.info(json.dumps({"event": event, **{key: value for key, value in fields.items() if value is not None}}, default=str, sort_keys=True))
