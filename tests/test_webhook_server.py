"""Tests for the webhook server."""

import json
from unittest.mock import patch

import pytest

from src.webhooks.server import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"


class TestWebhookValidation:
    def test_validation_token_returned(self, client):
        """RingCentral sends a Validation-Token header on subscription creation."""
        response = client.post(
            "/webhooks/ringcentral",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Validation-Token": "test-token-123"},
        )
        assert response.status_code == 200
        assert response.headers.get("Validation-Token") == "test-token-123"


class TestFaxWebhook:
    @patch("src.webhooks.server.handle_inbound_fax")
    @patch("src.webhooks.server.VERIFICATION_TOKEN", "")  # Disable sig check for test
    def test_fax_event_processed(self, mock_handler, client):
        mock_handler.return_value = {"message_id": "msg123"}

        payload = {
            "event": "/restapi/v1.0/account/~/extension/~/fax",
            "subscriptionId": "sub-1",
            "body": {
                "id": "msg123",
                "type": "Fax",
                "messageType": "Fax",
                "from": {"phoneNumber": "+18005551234"},
                "to": [{"phoneNumber": "+17608888888"}],
                "faxPageCount": 5,
            },
        }

        response = client.post(
            "/webhooks/ringcentral",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["type"] == "fax"
        mock_handler.assert_called_once()


class TestTelephonyWebhook:
    @patch("src.webhooks.server.VERIFICATION_TOKEN", "")
    def test_telephony_event_processed(self, client):
        payload = {
            "event": "/restapi/v1.0/account/~/extension/~/telephony/sessions",
            "subscriptionId": "sub-2",
            "body": {
                "sessionId": "sess-1",
                "parties": [
                    {
                        "direction": "Inbound",
                        "from": {"phoneNumber": "+18005559999"},
                        "status": {"code": "NoAnswer"},
                    }
                ],
            },
        }

        response = client.post(
            "/webhooks/ringcentral",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["type"] == "telephony"
