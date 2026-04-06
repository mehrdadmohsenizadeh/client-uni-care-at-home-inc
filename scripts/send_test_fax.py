#!/usr/bin/env python3
"""
Test Script — Send a test fax to verify the fax pipeline.

Usage:
    # Send a single-page test fax
    python scripts/send_test_fax.py --to +18005551234 --file test.pdf

    # Send a large batch fax
    python scripts/send_test_fax.py --to +18005551234 --file large_doc.pdf --batch
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fax.sender import get_fax_status, send_fax, send_fax_batch


def main():
    parser = argparse.ArgumentParser(description="Send a test fax via RingCentral API")
    parser.add_argument("--to", required=True, help="Destination fax number (E.164 format)")
    parser.add_argument("--file", required=True, help="Path to PDF file")
    parser.add_argument("--cover", default="Test fax from Uni Care At Home", help="Cover page text")
    parser.add_argument("--batch", action="store_true", help="Use batch mode for large PDFs")
    args = parser.parse_args()

    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        return 1

    print(f"=== Uni Care At Home — Test Fax ===")
    print(f"To:   {args.to}")
    print(f"File: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")
    print(f"Mode: {'Batch' if args.batch else 'Single'}")
    print()

    if args.batch:
        result = send_fax_batch(to=args.to, pdf_path=str(pdf_path), cover_page_text=args.cover)
        print(f"Batch ID: {result['batch_id']}")
        print(f"Total Pages: {result['total_pages']}")
        print(f"Chunks: {len(result['chunks'])}")
        print(f"Status: {result['status']}")
        print()
        for chunk in result["chunks"]:
            print(f"  Chunk {chunk.get('chunk_index', '?')}/{chunk.get('chunk_total', '?')}: "
                  f"{chunk.get('status', 'Unknown')} — ID: {chunk.get('message_id', 'N/A')}")
    else:
        result = send_fax(to=args.to, pdf_path=str(pdf_path), cover_page_text=args.cover)
        print(f"Message ID: {result['message_id']}")
        print(f"Status: {result['status']}")
        print(f"Pages: {result['pages']}")
        print(f"Timestamp: {result['timestamp']}")

        # Poll for delivery status
        print("\nChecking delivery status...")
        status = get_fax_status(result["message_id"])
        print(f"Current Status: {status['status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
