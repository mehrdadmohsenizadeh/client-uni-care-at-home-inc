#!/usr/bin/env python3
"""
Setup Script — Register all webhook subscriptions with RingCentral.

Run this once after deploying the webhook server:
    python scripts/setup_webhooks.py

Prerequisites:
    1. Webhook server is running and reachable via HTTPS
    2. .env file is configured with RC credentials
    3. WEBHOOK_BASE_URL points to your server
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.webhooks.subscriptions import create_all_subscriptions, list_subscriptions


def main():
    print("=== Uni Care At Home — Webhook Setup ===\n")

    # Check for existing subscriptions
    existing = list_subscriptions()
    if existing:
        print(f"Found {len(existing)} existing subscription(s):")
        for sub in existing:
            print(f"  ID: {sub['id']}  Status: {sub['status']}")
        print()

    # Create new subscriptions
    print("Creating webhook subscriptions...\n")
    subs = create_all_subscriptions()

    for sub in subs:
        status = "OK" if sub["status"] == "Active" else sub["status"]
        print(f"  [{status}] {sub['name']}")
        print(f"       ID: {sub['id']}")
        print(f"       Filters: {', '.join(sub['filters'])}")
        print()

    active = [s for s in subs if s["status"] == "Active"]
    print(f"Done. {len(active)}/{len(subs)} subscriptions active.")

    if len(active) < len(subs):
        print("\nWARNING: Some subscriptions failed. Check that your webhook URL")
        print("is reachable via HTTPS and returns the validation token correctly.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
