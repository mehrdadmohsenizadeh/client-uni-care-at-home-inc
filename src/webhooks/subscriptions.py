"""
Webhook Subscription Manager — Register and manage RingCentral webhooks.

Creates subscriptions for real-time event notifications:
- Inbound fax received
- Missed calls
- Voicemail received
- Message store changes (fax delivery status)

Usage:
    from src.webhooks.subscriptions import create_all_subscriptions

    subs = create_all_subscriptions()
    for sub in subs:
        print(f"Subscription {sub['id']}: {sub['status']}")
"""

import os

from dotenv import load_dotenv

from src.compliance.audit import audit_log
from src.core.client import get_client

load_dotenv()

WEBHOOK_URL = os.environ.get("WEBHOOK_BASE_URL", "") + "/webhooks/ringcentral"
VERIFICATION_TOKEN = os.environ.get("WEBHOOK_VERIFICATION_TOKEN", "")


def create_subscription(event_filters: list[str], name: str = "") -> dict:
    """
    Create a single webhook subscription.

    Args:
        event_filters: List of RingCentral event filter URIs
        name: Human-readable name for this subscription

    Returns:
        Subscription details dict
    """
    platform = get_client()

    body = {
        "eventFilters": event_filters,
        "deliveryMode": {
            "transportType": "WebHook",
            "address": WEBHOOK_URL,
            "verificationToken": VERIFICATION_TOKEN,
        },
        "expiresIn": 630720000,  # Max: 20 years (auto-renews)
    }

    response = platform.post("/restapi/v1.0/subscription", body)
    result = response.json()

    audit_log(
        event="webhook.subscription_created",
        data={
            "subscription_id": result.get("id"),
            "name": name,
            "filters": event_filters,
            "status": result.get("status"),
        },
    )

    return {
        "id": result.get("id"),
        "status": result.get("status"),
        "name": name,
        "filters": event_filters,
        "created": result.get("creationTime"),
        "expires": result.get("expirationTime"),
    }


def create_all_subscriptions() -> list[dict]:
    """
    Create all required webhook subscriptions for the UCaaS system.

    Returns list of created subscription details.
    """
    subscriptions = []

    # 1. Inbound fax notifications
    sub = create_subscription(
        event_filters=[
            "/restapi/v1.0/account/~/extension/~/fax?direction=Inbound",
        ],
        name="Inbound Fax",
    )
    subscriptions.append(sub)

    # 2. Telephony session events (missed calls, call status)
    sub = create_subscription(
        event_filters=[
            "/restapi/v1.0/account/~/extension/~/telephony/sessions",
        ],
        name="Telephony Sessions",
    )
    subscriptions.append(sub)

    # 3. Voicemail notifications
    sub = create_subscription(
        event_filters=[
            "/restapi/v1.0/account/~/extension/~/voicemail",
        ],
        name="Voicemail",
    )
    subscriptions.append(sub)

    # 4. Message store changes (fax delivery confirmations)
    sub = create_subscription(
        event_filters=[
            "/restapi/v1.0/account/~/extension/~/message-store",
        ],
        name="Message Store",
    )
    subscriptions.append(sub)

    return subscriptions


def list_subscriptions() -> list[dict]:
    """List all active webhook subscriptions."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/subscription")
    records = response.json().get("records", [])

    return [
        {
            "id": s.get("id"),
            "status": s.get("status"),
            "filters": s.get("eventFilters"),
            "created": s.get("creationTime"),
            "expires": s.get("expirationTime"),
        }
        for s in records
    ]


def delete_subscription(subscription_id: str) -> bool:
    """Delete a webhook subscription by ID."""
    platform = get_client()
    platform.delete(f"/restapi/v1.0/subscription/{subscription_id}")

    audit_log(
        event="webhook.subscription_deleted",
        data={"subscription_id": subscription_id},
    )

    return True


def delete_all_subscriptions() -> int:
    """Delete all webhook subscriptions. Returns count of deleted."""
    subs = list_subscriptions()
    for sub in subs:
        delete_subscription(sub["id"])
    return len(subs)
