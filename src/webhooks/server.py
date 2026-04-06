"""
Webhook Server — Receives real-time events from RingCentral.

Handles:
- Fax received notifications
- Missed call alerts
- Voicemail notifications
- Fax delivery status updates

This server must be deployed behind HTTPS (required for HIPAA).
Use gunicorn in production: gunicorn -w 4 -b 0.0.0.0:8443 src.webhooks.server:app

Usage:
    # Development
    python -m src.webhooks.server

    # Production
    gunicorn --certfile cert.pem --keyfile key.pem \
             -w 4 -b 0.0.0.0:443 src.webhooks.server:app
"""

import hashlib
import hmac
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

from src.compliance.audit import audit_log
from src.fax.receiver import handle_inbound_fax

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "change-me")

VERIFICATION_TOKEN = os.environ.get("WEBHOOK_VERIFICATION_TOKEN", "")


def verify_webhook_signature(request_data: bytes, signature: str) -> bool:
    """
    Verify the webhook request is genuinely from RingCentral.

    RingCentral signs webhook payloads with the verification token
    using HMAC-SHA1. We must validate this to prevent spoofed events.
    """
    if not VERIFICATION_TOKEN:
        return False

    expected = hmac.new(
        VERIFICATION_TOKEN.encode("utf-8"),
        request_data,
        hashlib.sha1,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


@app.route("/webhooks/ringcentral", methods=["POST"])
def ringcentral_webhook():
    """
    Main webhook endpoint for all RingCentral events.

    RingCentral sends a validation request first (with a validation token),
    then sends event notifications for subscribed events.
    """
    data = request.get_json(silent=True) or {}

    # Step 1: Handle initial validation (RingCentral sends this once on subscription)
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        audit_log(event="webhook.validated", data={"status": "ok"})
        return Response(
            status=200,
            headers={"Validation-Token": validation_token},
        )

    # Step 2: Verify signature on real events
    signature = request.headers.get("X-RingCentral-Signature", "")
    if VERIFICATION_TOKEN and not verify_webhook_signature(request.data, signature):
        audit_log(event="webhook.signature_failed", data={"ip": request.remote_addr})
        return jsonify({"error": "Invalid signature"}), 403

    # Step 3: Route event to appropriate handler
    event_type = data.get("event", "")
    subscription_id = data.get("subscriptionId", "")

    audit_log(
        event="webhook.received",
        data={
            "event_type": event_type,
            "subscription_id": subscription_id,
        },
    )

    # Fax received
    if "/fax" in event_type or _is_fax_event(data):
        result = handle_inbound_fax(data)
        return jsonify({"status": "processed", "type": "fax", "id": result.get("message_id")})

    # Missed call
    if "/telephony/sessions" in event_type:
        _handle_telephony_event(data)
        return jsonify({"status": "processed", "type": "telephony"})

    # Voicemail
    if "/voicemail" in event_type:
        _handle_voicemail_event(data)
        return jsonify({"status": "processed", "type": "voicemail"})

    # Message store change (covers fax status updates)
    if "/message-store" in event_type:
        _handle_message_store_event(data)
        return jsonify({"status": "processed", "type": "message_store"})

    # Unknown event type — log and accept
    audit_log(event="webhook.unhandled", data={"event_type": event_type})
    return jsonify({"status": "accepted", "type": "unknown"})


def _is_fax_event(data: dict) -> bool:
    """Check if the event payload is a fax message."""
    body = data.get("body", {})
    return body.get("type") == "Fax" or body.get("messageType") == "Fax"


def _handle_telephony_event(data: dict):
    """Process telephony session events (missed calls, call status changes)."""
    body = data.get("body", {})
    parties = body.get("parties", [])

    for party in parties:
        status = party.get("status", {}).get("code")
        direction = party.get("direction")
        caller = party.get("from", {}).get("phoneNumber", "unknown")

        if status == "NoAnswer":
            audit_log(
                event="call.missed",
                data={
                    "from": caller,
                    "direction": direction,
                    "session_id": body.get("sessionId"),
                },
            )


def _handle_voicemail_event(data: dict):
    """Process voicemail notifications."""
    body = data.get("body", {})
    audit_log(
        event="voicemail.received",
        data={
            "message_id": body.get("id"),
            "from": body.get("from", {}).get("phoneNumber", "unknown"),
            "duration": body.get("vmDuration"),
        },
    )


def _handle_message_store_event(data: dict):
    """Process message store changes (fax delivery confirmations, etc.)."""
    body = data.get("body", {})
    changes = body.get("changes", [])

    for change in changes:
        if change.get("type") == "Fax":
            audit_log(
                event="fax.status_update",
                data={
                    "new_count": change.get("newCount"),
                    "updated_count": change.get("updatedCount"),
                },
            )


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return jsonify({"status": "healthy", "service": "ucaas-webhook-server"})


if __name__ == "__main__":
    # Development only — use gunicorn + HTTPS in production
    print("WARNING: Running in development mode. Use gunicorn for production.")
    app.run(host="0.0.0.0", port=8443, debug=True)
