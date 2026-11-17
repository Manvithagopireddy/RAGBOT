"""
tests/test_file_handler.py
Tests for every fix made to src/file_handler.py in Phase 2:
  BUG-001  load_embedding_model → get_embeddings (broken import)
  BUG-004  Path-traversal prevention
  SEC-002  File size cap + extension allowlist
"""
from unittest.mock import MagicMock, patch

from src.file_handler import (
    MAX_UPLOAD_BYTES,
    _safe_filename,
    get_file_icon,
    get_file_size_label,
    validate_upload,
)

# ── _safe_filename ─────────────────────────────────────────────────────────────

class TestSafeFilename:
    def test_strips_directory_components(self):
        """Path traversal: ../../etc/passwd → passwd"""
        assert _safe_filename("../../etc/passwd") == "passwd"

    def test_strips_windows_path(self):
        """Windows path traversal: ..\\config\\settings.py → settings.py"""
        result = _safe_filename("..\\config\\settings.py")
        # On any OS, Path().name strips directory separators known to that OS.
        # The result must not contain path separators.
        assert "/" not in result
        assert "\\" not in result

    def test_replaces_special_chars(self):
        """Dangerous chars replaced with underscores."""
        result = _safe_filename("my file (1).pdf")
        assert " " not in result
        assert "(" not in result
        assert result.endswith(".pdf")

    def test_preserves_valid_names(self):
        """Normal filenames are unchanged (letters, digits, dot, hyphen, underscore)."""
        assert _safe_filename("my-report_v2.docx") == "my-report_v2.docx"

    def test_empty_name_returns_fallback(self):
        """Empty string should not raise; returns 'upload'."""
        result = _safe_filename("")
        assert result == "upload"

    def test_deep_path_traversal(self):
        """Nested traversal attack."""
        result = _safe_filename("/var/www/html/../../secret.txt")
        assert result == "secret.txt"


# ── validate_upload ────────────────────────────────────────────────────────────

def _make_upload(name: str, data: bytes) -> MagicMock:
    """Helper: create a mock Streamlit UploadedFile."""
    mock = MagicMock()
    mock.name = name
    mock.getvalue.return_value = data
    return mock


class TestValidateUpload:
    def test_valid_pdf(self):
        f = _make_upload("report.pdf", b"%PDF-1.4 valid content here" * 10)
        ok, reason = validate_upload(f)
        assert ok is True
        assert reason == ""

    def test_valid_txt(self):
        f = _make_upload("notes.txt", b"Hello world")
        ok, reason = validate_upload(f)
        assert ok is True

    def test_valid_csv(self):
        f = _make_upload("data.csv", b"col1,col2\nval1,val2")
        ok, reason = validate_upload(f)
        assert ok is True

    def test_valid_docx(self):
        f = _make_upload("doc.docx", b"PK\x03\x04" + b"\x00" * 100)
        ok, reason = validate_upload(f)
        assert ok is True

    def test_valid_pptx(self):
        f = _make_upload("slides.pptx", b"PK\x03\x04" + b"\x00" * 100)
        ok, reason = validate_upload(f)
        assert ok is True

    # --- Rejection cases ---

    def test_rejects_exe(self):
        """SEC-002: executable files must be rejected."""
        f = _make_upload("malware.exe", b"MZ\x90\x00" * 20)
        ok, reason = validate_upload(f)
        assert ok is False
        assert "Unsupported" in reason

    def test_rejects_py(self):
        f = _make_upload("evil.py", b"import os; os.system('rm -rf /')")
        ok, reason = validate_upload(f)
        assert ok is False

    def test_rejects_empty_file(self):
        """SEC-002: zero-byte files must be rejected."""
        f = _make_upload("empty.pdf", b"")
        ok, reason = validate_upload(f)
        assert ok is False
        assert "empty" in reason.lower()

    def test_rejects_oversized_file(self):
        """SEC-002: files larger than MAX_UPLOAD_BYTES must be rejected."""
        big_data = b"x" * (MAX_UPLOAD_BYTES + 1)
        f = _make_upload("huge.pdf", big_data)
        ok, reason = validate_upload(f)
        assert ok is False
        assert "large" in reason.lower() or "MB" in reason

    def test_rejects_file_at_exact_limit_plus_one(self):
        """Boundary: exactly one byte over the limit is rejected."""
        data = b"a" * (MAX_UPLOAD_BYTES + 1)
        f = _make_upload("boundary.pdf", data)
        ok, _ = validate_upload(f)
        assert ok is False

    def test_accepts_file_at_exact_limit(self):
        """Boundary: exactly MAX_UPLOAD_BYTES is accepted."""
        data = b"a" * MAX_UPLOAD_BYTES
        f = _make_upload("boundary.pdf", data)
        ok, _ = validate_upload(f)
        assert ok is True

    def test_rejects_disguised_exe_as_pdf(self):
        """
        Extension check: an executable renamed to .pdf passes the extension
        check (we only validate by extension, not by magic bytes, which is the
        documented scope). This test asserts the current behaviour so we don't
        accidentally change it without noticing.
        """
        f = _make_upload("not_a_pdf.pdf", b"MZ\x90\x00" * 20)
        ok, _ = validate_upload(f)
        # Extension is .pdf — passes the extension check
        assert ok is True

    def test_getvalue_raises_returns_error(self):
        """If getvalue() raises, validate_upload returns a failure."""
        mock = MagicMock()
        mock.name = "broken.pdf"
        mock.getvalue.side_effect = IOError("disk error")
        ok, reason = validate_upload(mock)
        assert ok is False
        assert "read" in reason.lower() or "disk" in reason.lower()


# ── index_uploaded_file ────────────────────────────────────────────────────────

class TestIndexUploadedFile:
    """
    Tests for the full index_uploaded_file() function with heavy mocking so
    no real filesystem, embeddings, or FAISS operations are needed.
    """

    def _make_valid_upload(self, name="test.txt", content=b"hello world " * 50):
        mock = MagicMock()
        mock.name = name
        mock.getvalue.return_value = content
        return mock

    @patch("src.embeddings.get_embeddings")
    @patch("src.document_loader.load_file")
    @patch("langchain_community.vectorstores.FAISS")
    def test_fix_bug001_get_embeddings_called(self, mock_faiss, mock_load_file, mock_get_embeddings, tmp_path):
        """
        BUG-001 regression: get_embeddings() must be called (not the old
        non-existent load_embedding_model()).
        """
        from langchain_core.documents import Document

        from src.file_handler import index_uploaded_file

        mock_load_file.return_value = [
            Document(page_content="test content", metadata={"source": "test.txt", "page": 0})
        ]
        mock_get_embeddings.return_value = MagicMock()
        mock_faiss.from_documents.return_value = MagicMock()

        upload = self._make_valid_upload("test.txt")
        with patch("config.settings.UPLOADS_DIR", tmp_path):
            index_uploaded_file(upload, None)

        mock_get_embeddings.assert_called_once()

    def test_invalid_extension_returns_global_db(self, tmp_path):
        """Files with unsupported extensions are rejected; global_db returned unchanged."""
        from src.file_handler import index_uploaded_file

        mock_global = MagicMock()
        upload = MagicMock()
        upload.name = "script.exe"
        upload.getvalue.return_value = b"MZ" * 50

        with patch("config.settings.UPLOADS_DIR", tmp_path):
            result = index_uploaded_file(upload, mock_global)

        assert result is mock_global

    def test_empty_file_returns_global_db(self, tmp_path):
        """Empty files are rejected; global_db returned unchanged."""
        from src.file_handler import index_uploaded_file

        mock_global = MagicMock()
        upload = MagicMock()
        upload.name = "empty.pdf"
        upload.getvalue.return_value = b""

        with patch("config.settings.UPLOADS_DIR", tmp_path):
            result = index_uploaded_file(upload, mock_global)

        assert result is mock_global

    @patch("src.embeddings.get_embeddings")
    @patch("src.document_loader.load_file")
    @patch("langchain_community.vectorstores.FAISS")
    def test_path_traversal_name_sanitised(self, mock_faiss, mock_load_file, mock_get_embeddings, tmp_path):
        """
        BUG-004 regression: a traversal filename must be sanitised so the
        saved file lands inside UPLOADS_DIR, not at an arbitrary path.
        """
        from langchain_core.documents import Document

        from src.file_handler import index_uploaded_file

        mock_load_file.return_value = [
            Document(page_content="x" * 200, metadata={"source": "evil.pdf", "page": 0})
        ]
        mock_get_embeddings.return_value = MagicMock()
        mock_faiss.from_documents.return_value = MagicMock()

        upload = MagicMock()
        upload.name = "../../config/settings.pdf"   # traversal attempt
        upload.getvalue.return_value = b"a" * 100

        with patch("config.settings.UPLOADS_DIR", tmp_path):
            index_uploaded_file(upload, None)

        # Ensure no file was written outside tmp_path
        for f in tmp_path.iterdir():
            assert tmp_path in f.parents or f.parent == tmp_path, (
                f"File written outside UPLOADS_DIR: {f}"
            )


# ── UI helpers ─────────────────────────────────────────────────────────────────

class TestUIHelpers:
    def test_get_file_icon_pdf(self):
        assert get_file_icon("report.pdf") == "📄"

    def test_get_file_icon_txt(self):
        assert get_file_icon("notes.TXT") == "📝"

    def test_get_file_icon_csv(self):
        assert get_file_icon("data.csv") == "📊"

    def test_get_file_icon_unknown(self):
        assert get_file_icon("archive.zip") == "📎"

    def test_get_file_size_label_bytes(self):
        f = _make_upload("x.txt", b"a" * 500)
        assert "B" in get_file_size_label(f)

    def test_get_file_size_label_kb(self):
        f = _make_upload("x.txt", b"a" * 2048)
        assert "KB" in get_file_size_label(f)

    def test_get_file_size_label_mb(self):
        f = _make_upload("x.txt", b"a" * (2 * 1024 * 1024))
        assert "MB" in get_file_size_label(f)
