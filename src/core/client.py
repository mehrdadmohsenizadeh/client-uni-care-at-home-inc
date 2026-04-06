"""
RingCentral API Client — Authenticated wrapper for all platform operations.

Authentication uses JWT (JSON Web Token) flow, which is the recommended
server-to-server auth method. No user interaction required.

Usage:
    from src.core.client import get_client

    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~/extension/~")
    print(response.json())
"""

import os
import sys

from dotenv import load_dotenv
from ringcentral import SDK

load_dotenv()

_sdk_instance = None


def get_sdk() -> SDK:
    """Return a singleton RingCentral SDK instance."""
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = SDK(
            client_id=os.environ["RC_CLIENT_ID"],
            client_secret=os.environ["RC_CLIENT_SECRET"],
            server=os.environ.get(
                "RC_SERVER_URL", "https://platform.ringcentral.com"
            ),
        )
    return _sdk_instance


def get_client():
    """
    Authenticate and return the RingCentral Platform client.

    Uses JWT authentication (no user interaction needed).
    The SDK handles token refresh automatically.
    """
    sdk = get_sdk()
    platform = sdk.platform()

    if not platform.logged_in():
        platform.login(jwt=os.environ["RC_JWT_TOKEN"])

    return platform


def get_account_info():
    """Retrieve basic account information — useful for verifying connectivity."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~")
    return response.json()


def list_extensions():
    """List all extensions on the account."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~/extension")
    return response.json().get("records", [])


if __name__ == "__main__":
    try:
        info = get_account_info()
        print(f"Connected to RingCentral account: {info.get('id')}")
        print(f"Company: {info.get('serviceInfo', {}).get('brand', {}).get('name')}")
        print(f"Status: {info.get('status')}")

        extensions = list_extensions()
        print(f"\nExtensions ({len(extensions)}):")
        for ext in extensions:
            print(f"  {ext.get('extensionNumber', 'N/A'):>5}  "
                  f"{ext.get('name', 'N/A'):<30}  "
                  f"{ext.get('status', 'N/A')}")
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
