"""
Phone Provisioning Manager — Register and manage SIP desk phones.

RingCentral supports Zero-Touch Provisioning (ZTP) for Yealink and Poly
desk phones. The process:

1. Register the phone's MAC address in RingCentral Admin
2. Assign it to a user/extension
3. Connect the phone to the network (PoE)
4. Phone boots, contacts RingCentral's provisioning server (rps.yealink.com)
5. Downloads its configuration automatically — no manual setup

This module provides API access to manage phone devices.

Usage:
    from src.provisioning.phones import list_devices, register_device
"""

from src.compliance.audit import audit_log
from src.core.client import get_client

# Supported phone models for ZTP
SUPPORTED_MODELS = {
    "Yealink T54W": {"type": "HardPhone", "features": ["color_screen", "wifi", "bluetooth", "poe"]},
    "Yealink T43U": {"type": "HardPhone", "features": ["color_screen", "poe", "usb"]},
    "Yealink W76P": {"type": "HardPhone", "features": ["dect", "cordless", "poe"]},
    "Yealink CP920": {"type": "HardPhone", "features": ["conference", "poe", "noise_proof"]},
}


def list_devices() -> list[dict]:
    """List all provisioned devices on the account."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~/device")
    records = response.json().get("records", [])

    return [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "model": d.get("model", {}).get("name"),
            "serial": d.get("serial"),
            "status": d.get("status"),
            "extension": d.get("extension", {}).get("extensionNumber"),
            "mac_address": _extract_mac(d),
        }
        for d in records
    ]


def _extract_mac(device: dict) -> str | None:
    """Extract MAC address from device emergency address or model info."""
    # MAC is typically available in the device's detailed info
    return device.get("macAddress")


def get_device_details(device_id: str) -> dict:
    """Get detailed info for a specific device."""
    platform = get_client()
    response = platform.get(f"/restapi/v1.0/account/~/device/{device_id}")
    return response.json()


def list_extension_devices(extension_id: str) -> list[dict]:
    """List all devices assigned to a specific extension."""
    platform = get_client()
    response = platform.get(
        f"/restapi/v1.0/account/~/extension/{extension_id}/device"
    )
    return response.json().get("records", [])


def provision_phone_checklist(model: str, mac_address: str, extension: int) -> dict:
    """
    Generate a provisioning checklist for a new desk phone.

    This is a helper — actual ZTP happens automatically when:
    1. MAC is registered in RingCentral Admin
    2. Phone is connected to network with internet access

    Args:
        model: Phone model name (e.g., "Yealink T54W")
        mac_address: MAC address (format: "AA:BB:CC:DD:EE:FF")
        extension: Extension number to assign

    Returns:
        Provisioning checklist dict
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}. Supported: {list(SUPPORTED_MODELS.keys())}")

    checklist = {
        "model": model,
        "mac_address": mac_address.upper(),
        "extension": extension,
        "features": SUPPORTED_MODELS[model]["features"],
        "steps": [
            f"1. Log into RingCentral Admin Portal > Phone System > Phones & Devices",
            f"2. Click 'Add Device' > Select '{model}'",
            f"3. Enter MAC address: {mac_address.upper()}",
            f"4. Assign to extension {extension}",
            f"5. Connect phone to PoE switch (VLAN 20 - Voice)",
            f"6. Phone will auto-provision via ZTP (1-3 minutes)",
            f"7. Verify: phone displays extension {extension} and company name",
        ],
        "network_requirements": [
            "PoE (802.3af) on switch port",
            "VLAN 20 (Voice) with DHCP",
            "Internet access (HTTPS to *.ringcentral.com)",
            "DNS resolution",
            "NTP access (time sync)",
        ],
    }

    audit_log(
        event="provisioning.checklist_generated",
        data={
            "model": model,
            "extension": extension,
        },
    )

    return checklist
