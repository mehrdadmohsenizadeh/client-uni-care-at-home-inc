#!/usr/bin/env python3
"""
System Health Check — Verify all UCaaS components are operational.

Run periodically or as part of deployment verification:
    python scripts/check_system.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_api_connection():
    """Verify RingCentral API connectivity."""
    print("  Checking API connection...", end=" ")
    try:
        from src.core.client import get_account_info
        info = get_account_info()
        print(f"OK (Account: {info.get('id')})")
        return True
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_extensions():
    """Verify expected extensions exist."""
    print("  Checking extensions...", end=" ")
    try:
        from src.core.client import list_extensions
        extensions = list_extensions()
        print(f"OK ({len(extensions)} extensions)")
        return True
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_webhooks():
    """Verify webhook subscriptions are active."""
    print("  Checking webhook subscriptions...", end=" ")
    try:
        from src.webhooks.subscriptions import list_subscriptions
        subs = list_subscriptions()
        active = [s for s in subs if s["status"] == "Active"]
        print(f"OK ({len(active)} active / {len(subs)} total)")
        return len(active) > 0
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_devices():
    """Verify provisioned devices."""
    print("  Checking provisioned devices...", end=" ")
    try:
        from src.provisioning.phones import list_devices
        devices = list_devices()
        online = [d for d in devices if d.get("status") == "Online"]
        print(f"OK ({len(online)} online / {len(devices)} total)")
        return True
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_audit_log():
    """Verify audit log is writable."""
    print("  Checking audit log...", end=" ")
    try:
        from src.compliance.audit import audit_log, get_audit_log_path
        log_path = get_audit_log_path()
        audit_log(event="system.health_check", data={"status": "ok"})
        print(f"OK ({log_path})")
        return True
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def main():
    print("=== Uni Care At Home — System Health Check ===\n")

    checks = [
        ("API Connection", check_api_connection),
        ("Extensions", check_extensions),
        ("Webhooks", check_webhooks),
        ("Devices", check_devices),
        ("Audit Log", check_audit_log),
    ]

    results = []
    for name, check_fn in checks:
        results.append(check_fn())

    passed = sum(results)
    total = len(results)
    print(f"\nResult: {passed}/{total} checks passed")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
