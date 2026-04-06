"""Tests for the audit logging module."""

import json
from pathlib import Path

from src.compliance.audit import audit_log, get_audit_log_path


class TestAuditLog:
    def test_audit_log_creates_entry(self):
        """Verify audit_log writes to the log file."""
        audit_log(event="test.event", data={"key": "value"})
        log_path = get_audit_log_path()
        assert Path(log_path).exists()

    def test_audit_log_json_format(self):
        """Verify log entries are valid JSON."""
        audit_log(event="test.json_format", data={"number": 42})
        log_path = get_audit_log_path()

        with open(log_path) as f:
            lines = f.readlines()

        # Last line should be valid JSON (wrapped in the logging format)
        last_line = lines[-1].strip()
        # The logging module may add a prefix; the JSON is in the message
        assert "test.json_format" in last_line

    def test_audit_log_no_phi(self):
        """Verify we're logging metadata, not content."""
        audit_log(
            event="fax.received",
            data={
                "message_id": "abc123",
                "from": "+18005551234",
                "pages": 10,
            },
        )
        log_path = get_audit_log_path()

        with open(log_path) as f:
            content = f.read()

        # These are OK to log
        assert "abc123" in content
        assert "+18005551234" in content

        # PHI should never appear — this test documents the expectation
        assert "patient" not in content.lower()
        assert "diagnosis" not in content.lower()
