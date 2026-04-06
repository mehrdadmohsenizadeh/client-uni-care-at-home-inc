"""
IVR / Auto-Attendant Manager — Programmatic configuration of call menus.

While the IVR is typically configured via the RingCentral Admin Portal
(drag-and-drop), this module provides API-driven management for:
- Reading current IVR configuration
- Updating business hours
- Modifying menu prompts programmatically
- Managing ring group membership

Usage:
    from src.ivr.manager import get_ivr_config, update_business_hours
"""

from src.core.client import get_client


def get_company_info() -> dict:
    """Get company-level phone system information."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~")
    return response.json()


def get_ivr_config() -> dict:
    """
    Retrieve the current IVR / Auto-Attendant configuration.

    Returns the greeting settings, menu options, and routing rules
    for the main company number.
    """
    platform = get_client()

    # Get the auto-receptionist extension (typically the main site IVR)
    response = platform.get("/restapi/v1.0/account/~/ivr-menus")
    return response.json()


def get_business_hours() -> dict:
    """Get the company's business hours schedule."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~/business-hours")
    return response.json()


def update_business_hours(schedule: dict) -> dict:
    """
    Update business hours for the company.

    Args:
        schedule: Dict matching RingCentral's business hours format:
            {
                "schedule": {
                    "weeklyRanges": {
                        "monday": [{"from": "08:00", "to": "17:00"}],
                        "tuesday": [{"from": "08:00", "to": "17:00"}],
                        ...
                    }
                }
            }

    Returns:
        Updated business hours configuration
    """
    platform = get_client()
    response = platform.put("/restapi/v1.0/account/~/business-hours", schedule)
    return response.json()


def list_call_queues() -> list[dict]:
    """List all call queues (ring groups) on the account."""
    platform = get_client()
    response = platform.get("/restapi/v1.0/account/~/call-queues")
    records = response.json().get("records", [])

    return [
        {
            "id": q.get("id"),
            "name": q.get("name"),
            "extension": q.get("extensionNumber"),
            "status": q.get("status"),
        }
        for q in records
    ]


def get_call_queue_members(queue_id: str) -> list[dict]:
    """Get members of a specific call queue / ring group."""
    platform = get_client()
    response = platform.get(f"/restapi/v1.0/account/~/call-queues/{queue_id}/members")
    records = response.json().get("records", [])

    return [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "extension": m.get("extensionNumber"),
        }
        for m in records
    ]


def add_call_queue_member(queue_id: str, extension_id: str) -> dict:
    """Add a member (extension) to a ring group."""
    platform = get_client()
    response = platform.post(
        f"/restapi/v1.0/account/~/call-queues/{queue_id}/members",
        {"records": [{"id": extension_id}]},
    )
    return response.json()


def get_call_recordings(date_from: str, date_to: str, extension_id: str = "~") -> list[dict]:
    """
    Retrieve call recording metadata for compliance/audit purposes.

    Args:
        date_from: ISO 8601 start date
        date_to: ISO 8601 end date
        extension_id: Specific extension or "~" for all

    Returns:
        List of recording metadata (IDs, timestamps, durations — no audio content)
    """
    platform = get_client()
    response = platform.get(
        f"/restapi/v1.0/account/~/extension/{extension_id}/call-log",
        {
            "dateFrom": date_from,
            "dateTo": date_to,
            "withRecording": True,
            "perPage": 250,
        },
    )

    records = response.json().get("records", [])

    return [
        {
            "id": r.get("id"),
            "direction": r.get("direction"),
            "from": r.get("from", {}).get("phoneNumber"),
            "to": r.get("to", {}).get("phoneNumber"),
            "duration": r.get("duration"),
            "recording_id": r.get("recording", {}).get("id") if r.get("recording") else None,
            "started_at": r.get("startTime"),
        }
        for r in records
        if r.get("recording")
    ]
