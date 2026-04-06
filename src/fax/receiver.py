"""
Inbound Fax Receiver — Webhook handler for incoming faxes.

When a fax arrives on 760-888-8888, RingCentral:
1. Detects CNG tone → routes to fax extension
2. Receives and renders the fax server-side
3. Fires a webhook to our server with fax metadata

This module processes those webhooks and logs them for audit.
It does NOT download or store the fax PDF locally (HIPAA: fax content
stays in RingCentral's encrypted cloud).

Usage:
    # This is called by the webhook server (src/webhooks/server.py)
    from src.fax.receiver import handle_inbound_fax

    handle_inbound_fax(webhook_payload)
"""

from src.compliance.audit import audit_log
from src.core.client import get_client


def handle_inbound_fax(event_body: dict) -> dict:
    """
    Process an inbound fax webhook event.

    Args:
        event_body: The webhook payload from RingCentral

    Returns:
        dict with processed fax metadata (no PHI)
    """
    message = event_body.get("body", {})

    fax_info = {
        "message_id": message.get("id"),
        "from": message.get("from", {}).get("phoneNumber", "unknown"),
        "to": message.get("to", [{}])[0].get("phoneNumber", "unknown"),
        "pages": message.get("faxPageCount", 0),
        "resolution": message.get("faxResolution", "unknown"),
        "status": message.get("messageStatus", "unknown"),
        "received_at": message.get("creationTime"),
        "direction": "Inbound",
    }

    audit_log(
        event="fax.received",
        data={
            "message_id": fax_info["message_id"],
            "from": fax_info["from"],
            "pages": fax_info["pages"],
            "status": fax_info["status"],
        },
    )

    return fax_info


def list_received_faxes(date_from: str = None, date_to: str = None) -> list[dict]:
    """
    List received faxes from the message store.

    Args:
        date_from: ISO 8601 date string (e.g., "2026-04-01T00:00:00Z")
        date_to: ISO 8601 date string

    Returns:
        List of fax metadata dicts (no PHI — only IDs, dates, page counts)
    """
    platform = get_client()

    params = {
        "messageType": "Fax",
        "direction": "Inbound",
        "perPage": 100,
    }

    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to

    response = platform.get(
        "/restapi/v1.0/account/~/extension/~/message-store",
        params,
    )

    records = response.json().get("records", [])

    return [
        {
            "message_id": r.get("id"),
            "from": r.get("from", {}).get("phoneNumber"),
            "pages": r.get("faxPageCount"),
            "status": r.get("messageStatus"),
            "received_at": r.get("creationTime"),
        }
        for r in records
    ]


def get_fax_pdf_url(message_id: str) -> str:
    """
    Get a time-limited download URL for a fax PDF.

    HIPAA Note: The URL is temporary and requires authentication.
    The PDF should be viewed/processed in memory and NOT saved to disk
    unless absolutely necessary (and then encrypted).

    Args:
        message_id: RingCentral message ID

    Returns:
        Authenticated URL string for PDF download
    """
    platform = get_client()
    response = platform.get(
        f"/restapi/v1.0/account/~/extension/~/message-store/{message_id}"
    )
    message = response.json()

    attachments = message.get("attachments", [])
    for attachment in attachments:
        if attachment.get("contentType") == "application/pdf":
            # The URI requires the auth token to download
            return attachment.get("uri")

    raise ValueError(f"No PDF attachment found for message {message_id}")
