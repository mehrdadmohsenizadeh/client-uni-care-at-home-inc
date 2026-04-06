"""
High-Volume Fax Sender — Store-and-Forward with Batch Support.

Handles PDFs of any size by splitting into ≤200-page chunks and tracking
them as a single logical batch. Each chunk is sent via RingCentral's
fax API with automatic server-side retries.

Usage:
    from src.fax.sender import send_fax, send_fax_batch

    # Single fax (up to 200 pages)
    result = send_fax(
        to="+18005551234",
        pdf_path="/path/to/document.pdf",
        cover_page_text="Attn: Billing Department"
    )

    # Large batch (any size — auto-splits)
    results = send_fax_batch(
        to="+18005551234",
        pdf_path="/path/to/large_document.pdf",
        cover_page_text="Patient Records — 450 pages"
    )
"""

import os
import uuid
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter

from src.compliance.audit import audit_log
from src.core.client import get_client

MAX_PAGES_PER_FAX = 200
GOLDEN_NUMBER = os.environ.get("RC_GOLDEN_NUMBER", "+17608888888")


def send_fax(to: str, pdf_path: str, cover_page_text: str = "") -> dict:
    """
    Send a single fax via RingCentral API.

    Args:
        to: Destination fax number in E.164 format (e.g., "+18005551234")
        pdf_path: Path to the PDF file to send
        cover_page_text: Optional text for the cover page

    Returns:
        dict with keys: message_id, status, pages, timestamp
    """
    platform = get_client()
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    if page_count > MAX_PAGES_PER_FAX:
        raise ValueError(
            f"PDF has {page_count} pages (max {MAX_PAGES_PER_FAX}). "
            f"Use send_fax_batch() for large documents."
        )

    # Build the multipart request
    body = {
        "to": [{"phoneNumber": to}],
        "faxResolution": "High",
    }

    if cover_page_text:
        body["coverPageText"] = cover_page_text

    # RingCentral fax API uses multipart form: JSON body + file attachment
    with open(pdf_path, "rb") as pdf_file:
        attachments = [
            ("json", ("request.json", __import__("json").dumps(body), "application/json")),
            ("attachment", (pdf_path.name, pdf_file, "application/pdf")),
        ]

        response = platform.post(
            "/restapi/v1.0/account/~/extension/~/fax",
            body,
            files=[("attachment", (pdf_path.name, open(pdf_path, "rb"), "application/pdf"))],
        )

    result = response.json()
    message_id = result.get("id")

    audit_log(
        event="fax.sent",
        data={
            "message_id": message_id,
            "to": to,
            "from": GOLDEN_NUMBER,
            "pages": page_count,
            "file_name": pdf_path.name,
            "status": result.get("messageStatus", "Queued"),
        },
    )

    return {
        "message_id": message_id,
        "status": result.get("messageStatus", "Queued"),
        "pages": page_count,
        "timestamp": result.get("creationTime"),
    }


def split_pdf(pdf_path: str, max_pages: int = MAX_PAGES_PER_FAX) -> list[str]:
    """
    Split a large PDF into smaller chunks.

    Returns a list of temporary file paths for each chunk.
    """
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    chunks = []

    for start in range(0, total_pages, max_pages):
        end = min(start + max_pages, total_pages)
        writer = PdfWriter()

        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        chunk_path = f"/tmp/fax_chunk_{start+1}_{end}.pdf"
        with open(chunk_path, "wb") as f:
            writer.write(f)

        chunks.append(chunk_path)

    return chunks


def send_fax_batch(to: str, pdf_path: str, cover_page_text: str = "") -> dict:
    """
    Send a large PDF as multiple fax transmissions, tracked as one batch.

    Automatically splits PDFs exceeding 200 pages into chunks.
    Each chunk is sent sequentially (to avoid overwhelming the recipient's
    fax machine). The batch is tracked with a unique batch ID.

    Args:
        to: Destination fax number in E.164 format
        pdf_path: Path to the PDF file
        cover_page_text: Optional cover page text (applied to first chunk only)

    Returns:
        dict with keys: batch_id, chunks (list), total_pages, status
    """
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"

    audit_log(
        event="fax.batch.started",
        data={
            "batch_id": batch_id,
            "to": to,
            "total_pages": total_pages,
            "file_name": Path(pdf_path).name,
        },
    )

    # If small enough, send as single fax
    if total_pages <= MAX_PAGES_PER_FAX:
        result = send_fax(to=to, pdf_path=pdf_path, cover_page_text=cover_page_text)
        return {
            "batch_id": batch_id,
            "chunks": [result],
            "total_pages": total_pages,
            "status": "complete",
        }

    # Split and send each chunk
    chunk_paths = split_pdf(pdf_path)
    chunk_results = []

    for i, chunk_path in enumerate(chunk_paths):
        cover = cover_page_text if i == 0 else f"(Continued — Part {i + 1} of {len(chunk_paths)})"

        try:
            result = send_fax(to=to, pdf_path=chunk_path, cover_page_text=cover)
            result["chunk_index"] = i + 1
            result["chunk_total"] = len(chunk_paths)
            chunk_results.append(result)
        except Exception as e:
            chunk_results.append({
                "chunk_index": i + 1,
                "chunk_total": len(chunk_paths),
                "status": "Failed",
                "error": str(e),
            })
        finally:
            # Clean up temp file
            Path(chunk_path).unlink(missing_ok=True)

    failed = [c for c in chunk_results if c.get("status") == "Failed"]
    status = "complete" if not failed else "partial_failure"

    audit_log(
        event="fax.batch.completed",
        data={
            "batch_id": batch_id,
            "total_pages": total_pages,
            "chunks_sent": len(chunk_results),
            "chunks_failed": len(failed),
            "status": status,
        },
    )

    return {
        "batch_id": batch_id,
        "chunks": chunk_results,
        "total_pages": total_pages,
        "status": status,
    }


def get_fax_status(message_id: str) -> dict:
    """
    Check the delivery status of a sent fax.

    Args:
        message_id: The RingCentral message ID returned from send_fax()

    Returns:
        dict with delivery status details
    """
    platform = get_client()
    response = platform.get(
        f"/restapi/v1.0/account/~/extension/~/message-store/{message_id}"
    )
    result = response.json()

    return {
        "message_id": message_id,
        "status": result.get("messageStatus"),
        "fax_resolution": result.get("faxResolution"),
        "pages": result.get("faxPageCount"),
        "created": result.get("creationTime"),
        "last_modified": result.get("lastModifiedTime"),
    }
