"""
HIPAA-Compliant Audit Logger.

Structured logging for all UCaaS system events. Logs are:
- Structured (JSON format for machine parsing)
- Timestamped (UTC)
- Immutable (append-only log files)
- PHI-free (NEVER log patient data, fax content, or call audio)

Log output goes to:
1. Structured JSON file (for SIEM/audit tools)
2. Console (for development/debugging)

Usage:
    from src.compliance.audit import audit_log

    audit_log(
        event="fax.sent",
        data={"message_id": "abc123", "to": "+18005551234", "pages": 50}
    )
"""

import logging
import os
from pathlib import Path

import structlog

# Configure log directory
LOG_DIR = os.environ.get("AUDIT_LOG_DIR", "/tmp/unicare_audit_logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# File handler for persistent audit trail
_file_handler = logging.FileHandler(os.path.join(LOG_DIR, "audit.jsonl"))
_file_handler.setLevel(logging.INFO)
_file_logger = logging.getLogger("ucaas.audit")
_file_logger.addHandler(_file_handler)
_file_logger.setLevel(logging.INFO)

# Structlog logger for console output
_logger = structlog.get_logger("ucaas.audit")


def audit_log(event: str, data: dict | None = None, level: str = "info"):
    """
    Write a structured audit log entry.

    Args:
        event: Event identifier (e.g., "fax.sent", "call.missed", "webhook.received")
        data: Structured metadata for the event (MUST NOT contain PHI)
        level: Log level — "info", "warning", "error"

    HIPAA Rules:
        - NEVER include patient names, DOB, SSN, or medical record numbers
        - NEVER include fax content or call audio transcripts
        - Phone numbers are OK (they are not PHI in isolation)
        - Message IDs are OK (they are opaque identifiers)
    """
    if data is None:
        data = {}

    log_entry = {"event": event, **data}

    # Write to structured log file (for audit/SIEM)
    import json
    from datetime import datetime, timezone

    file_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        **data,
    }
    _file_logger.info(json.dumps(file_entry))

    # Write to console via structlog
    log_func = getattr(_logger, level, _logger.info)
    log_func(event, **data)


def get_audit_log_path() -> str:
    """Return the path to the current audit log file."""
    return os.path.join(LOG_DIR, "audit.jsonl")
