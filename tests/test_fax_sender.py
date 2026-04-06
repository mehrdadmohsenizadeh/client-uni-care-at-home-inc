"""Tests for the fax sender module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.fax.sender import MAX_PAGES_PER_FAX, split_pdf


class TestSplitPdf:
    """Tests for PDF splitting logic."""

    def _create_test_pdf(self, num_pages: int) -> str:
        """Create a temporary PDF with the specified number of blank pages."""
        from PyPDF2 import PdfWriter

        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width=612, height=792)  # Letter size

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        writer.write(tmp)
        tmp.close()
        return tmp.name

    def test_split_small_pdf(self):
        """A PDF under the limit should produce a single chunk."""
        pdf_path = self._create_test_pdf(50)
        try:
            chunks = split_pdf(pdf_path, max_pages=200)
            assert len(chunks) == 1
        finally:
            Path(pdf_path).unlink(missing_ok=True)
            for c in chunks:
                Path(c).unlink(missing_ok=True)

    def test_split_exact_boundary(self):
        """A PDF exactly at the limit should produce one chunk."""
        pdf_path = self._create_test_pdf(200)
        try:
            chunks = split_pdf(pdf_path, max_pages=200)
            assert len(chunks) == 1
        finally:
            Path(pdf_path).unlink(missing_ok=True)
            for c in chunks:
                Path(c).unlink(missing_ok=True)

    def test_split_large_pdf(self):
        """A PDF over the limit should be split into multiple chunks."""
        pdf_path = self._create_test_pdf(450)
        try:
            chunks = split_pdf(pdf_path, max_pages=200)
            assert len(chunks) == 3  # 200 + 200 + 50

            # Verify page counts
            from PyPDF2 import PdfReader

            assert len(PdfReader(chunks[0]).pages) == 200
            assert len(PdfReader(chunks[1]).pages) == 200
            assert len(PdfReader(chunks[2]).pages) == 50
        finally:
            Path(pdf_path).unlink(missing_ok=True)
            for c in chunks:
                Path(c).unlink(missing_ok=True)

    def test_split_single_page(self):
        """A single-page PDF should produce one chunk."""
        pdf_path = self._create_test_pdf(1)
        try:
            chunks = split_pdf(pdf_path, max_pages=200)
            assert len(chunks) == 1
        finally:
            Path(pdf_path).unlink(missing_ok=True)
            for c in chunks:
                Path(c).unlink(missing_ok=True)


class TestMaxPagesConstant:
    def test_max_pages_is_200(self):
        assert MAX_PAGES_PER_FAX == 200
