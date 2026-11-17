"""
tests/test_document_loader.py  (Phase 2 — new file)
Tests for every fix in src/document_loader.py:
  • 0-indexed page metadata stored consistently
  • source metadata always equals basename
  • Empty / malformed file handling (no exceptions raised)
  • CSV row guard (empty rows skipped)
  • DOCX table text extraction
  • PPTX empty-slide skip
  • load_all_documents: sorted order, non-existent dir creation
"""
import csv
import sys
from unittest.mock import MagicMock, patch

from src.document_loader import (
    load_all_documents,
    load_csv_file,
    load_docx_file,
    load_file,
    load_pdf_file,
    load_pptx_file,
    load_txt_file,
)

# ── load_txt_file ──────────────────────────────────────────────────────────────

class TestLoadTxtFile:
    def test_loads_basic_text(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!", encoding="utf-8")
        docs = load_txt_file(f)
        assert len(docs) == 1
        assert "Hello, world!" in docs[0].page_content

    def test_metadata_source_is_basename(self, tmp_path):
        f = tmp_path / "my_file.txt"
        f.write_text("content", encoding="utf-8")
        docs = load_txt_file(f)
        assert docs[0].metadata["source"] == "my_file.txt"

    def test_metadata_page_is_zero_indexed(self, tmp_path):
        """Phase 2 fix: page stored as 0, not 1."""
        f = tmp_path / "file.txt"
        f.write_text("text", encoding="utf-8")
        docs = load_txt_file(f)
        assert docs[0].metadata["page"] == 0

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        docs = load_txt_file(f)
        assert docs == []

    def test_whitespace_only_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "ws.txt"
        f.write_text("   \n\t  ", encoding="utf-8")
        docs = load_txt_file(f)
        assert docs == []

    def test_non_utf8_chars_handled_gracefully(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes(b"caf\xe9 au lait")  # Latin-1 encoding
        docs = load_txt_file(f)
        # errors="ignore" so no exception, some chars may be dropped
        assert len(docs) == 1

    def test_missing_file_returns_empty_list(self, tmp_path):
        docs = load_txt_file(tmp_path / "ghost.txt")
        assert docs == []


# ── load_csv_file ──────────────────────────────────────────────────────────────

class TestLoadCsvFile:
    def _write_csv(self, path, rows, header=None):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if header:
                writer.writerow(header)
            writer.writerows(rows)

    def test_loads_rows_as_documents(self, tmp_path):
        f = tmp_path / "data.csv"
        self._write_csv(f, [["Alice", "30"], ["Bob", "25"]], header=["name", "age"])
        docs = load_csv_file(f)
        assert len(docs) == 2

    def test_metadata_source_is_basename(self, tmp_path):
        f = tmp_path / "data.csv"
        self._write_csv(f, [["a", "1"]], header=["col1", "col2"])
        docs = load_csv_file(f)
        assert docs[0].metadata["source"] == "data.csv"

    def test_metadata_page_is_0indexed_row_number(self, tmp_path):
        """Phase 2 fix: row 0 stored as page=0."""
        f = tmp_path / "data.csv"
        self._write_csv(f, [["r1"], ["r2"], ["r3"]], header=["val"])
        docs = load_csv_file(f)
        assert docs[0].metadata["page"] == 0
        assert docs[1].metadata["page"] == 1
        assert docs[2].metadata["page"] == 2

    def test_empty_rows_are_skipped(self, tmp_path):
        """Phase 2 fix: empty CSV rows must not create empty Documents."""
        f = tmp_path / "sparse.csv"
        self._write_csv(f, [["Alice", "30"], ["", ""], ["Bob", "25"]], header=["name", "age"])
        docs = load_csv_file(f)
        # The empty row ("" | "") should be skipped
        assert len(docs) == 2
        for doc in docs:
            assert doc.page_content.strip() != ""

    def test_all_empty_rows_returns_empty_list(self, tmp_path):
        f = tmp_path / "empty_rows.csv"
        self._write_csv(f, [["", ""], ["", ""]], header=["a", "b"])
        docs = load_csv_file(f)
        assert docs == []

    def test_missing_file_returns_empty_list(self, tmp_path):
        docs = load_csv_file(tmp_path / "ghost.csv")
        assert docs == []


# ── load_pdf_file ──────────────────────────────────────────────────────────────

class TestLoadPdfFile:
    def test_source_set_to_basename(self, tmp_path):
        """Even though we mock PyPDFLoader, source must be set to basename."""
        from langchain_core.documents import Document as LC_Doc
        fake_doc = LC_Doc(page_content="page text", metadata={"source": "/full/path/file.pdf", "page": 0})

        with patch("src.document_loader.PyPDFLoader") as MockLoader:
            instance = MockLoader.return_value
            instance.load.return_value = [fake_doc]
            docs = load_pdf_file(tmp_path / "file.pdf")

        assert docs[0].metadata["source"] == "file.pdf"

    def test_page_coerced_to_int(self, tmp_path):
        """Phase 2 fix: page must always be an int."""
        from langchain_core.documents import Document as LC_Doc
        fake_doc = LC_Doc(page_content="text", metadata={"source": "f.pdf", "page": "2"})

        with patch("src.document_loader.PyPDFLoader") as MockLoader:
            instance = MockLoader.return_value
            instance.load.return_value = [fake_doc]
            docs = load_pdf_file(tmp_path / "f.pdf")

        assert isinstance(docs[0].metadata["page"], int)
        assert docs[0].metadata["page"] == 2

    def test_loader_exception_returns_empty(self, tmp_path):
        """Malformed PDF must not propagate exception."""
        with patch("src.document_loader.PyPDFLoader") as MockLoader:
            MockLoader.side_effect = Exception("corrupted PDF")
            docs = load_pdf_file(tmp_path / "bad.pdf")
        assert docs == []

    def test_load_returns_empty_returns_empty_list(self, tmp_path):
        with patch("src.document_loader.PyPDFLoader") as MockLoader:
            instance = MockLoader.return_value
            instance.load.return_value = []
            docs = load_pdf_file(tmp_path / "blank.pdf")
        assert docs == []


# ── load_docx_file ─────────────────────────────────────────────────────────────

class TestLoadDocxFile:
    def _make_mock_docx(self, paragraphs=None, tables=None):
        """Build a minimal python-docx Document mock."""
        mock_doc = MagicMock()

        para_mocks = []
        for text in (paragraphs or []):
            p = MagicMock()
            p.text = text
            para_mocks.append(p)
        mock_doc.paragraphs = para_mocks

        table_mocks = []
        for table_data in (tables or []):
            tbl = MagicMock()
            row_mocks = []
            for row_data in table_data:
                row = MagicMock()
                cell_mocks = []
                for cell_text in row_data:
                    cell = MagicMock()
                    cell.text = cell_text
                    cell_mocks.append(cell)
                row.cells = cell_mocks
                row_mocks.append(row)
            tbl.rows = row_mocks
            table_mocks.append(tbl)
        mock_doc.tables = table_mocks

        return mock_doc

    def test_loads_paragraph_text(self, tmp_path):
        mock_doc = self._make_mock_docx(paragraphs=["Hello", "World"])
        with patch("docx.Document", return_value=mock_doc):
            docs = load_docx_file(tmp_path / "test.docx")
        assert len(docs) == 1
        assert "Hello" in docs[0].page_content
        assert "World" in docs[0].page_content

    def test_loads_table_text(self, tmp_path):
        """Phase 2 fix: table cell text must be extracted."""
        mock_doc = self._make_mock_docx(
            paragraphs=["Intro"],
            tables=[[["Name", "Age"], ["Alice", "30"]]]
        )
        with patch("docx.Document", return_value=mock_doc):
            docs = load_docx_file(tmp_path / "report.docx")
        content = docs[0].page_content
        assert "Name" in content or "Alice" in content

    def test_metadata_page_is_zero(self, tmp_path):
        """DOCX has no native pages — page stored as 0."""
        mock_doc = self._make_mock_docx(paragraphs=["text"])
        with patch("docx.Document", return_value=mock_doc):
            docs = load_docx_file(tmp_path / "d.docx")
        assert docs[0].metadata["page"] == 0

    def test_metadata_source_is_basename(self, tmp_path):
        mock_doc = self._make_mock_docx(paragraphs=["text"])
        with patch("docx.Document", return_value=mock_doc):
            docs = load_docx_file(tmp_path / "my_doc.docx")
        assert docs[0].metadata["source"] == "my_doc.docx"

    def test_empty_docx_returns_empty_list(self, tmp_path):
        mock_doc = self._make_mock_docx(paragraphs=["", "  "], tables=[])
        with patch("docx.Document", return_value=mock_doc):
            docs = load_docx_file(tmp_path / "empty.docx")
        assert docs == []

    def test_import_error_returns_empty(self, tmp_path):
        """python-docx not installed → returns empty list, no exception."""
        with patch.dict(sys.modules, {"docx": None}):
            docs = load_docx_file(tmp_path / "d.docx")
        assert docs == []

    def test_corrupt_docx_returns_empty(self, tmp_path):
        with patch("docx.Document", side_effect=Exception("bad zip")):
            docs = load_docx_file(tmp_path / "bad.docx")
        assert docs == []


# ── load_pptx_file ─────────────────────────────────────────────────────────────

class TestLoadPptxFile:
    def _make_mock_pptx(self, slides_text):
        """slides_text: list of lists of shape texts per slide."""
        prs = MagicMock()
        slide_mocks = []
        for slide_shapes in slides_text:
            slide = MagicMock()
            shape_mocks = []
            for txt in slide_shapes:
                shape = MagicMock()
                shape.text = txt
                shape_mocks.append(shape)
            slide.shapes = shape_mocks
            slide_mocks.append(slide)
        prs.slides = slide_mocks
        return prs

    def test_loads_slide_text(self, tmp_path):
        prs = self._make_mock_pptx([["Slide 1 Title", "Bullet point"]])
        with patch("pptx.Presentation", return_value=prs):
            docs = load_pptx_file(tmp_path / "deck.pptx")
        assert len(docs) == 1
        assert "Slide 1 Title" in docs[0].page_content

    def test_empty_slides_skipped(self, tmp_path):
        """Phase 2 fix: slides with no text must be silently skipped."""
        prs = self._make_mock_pptx([[""], ["Real content"], [""]])
        with patch("pptx.Presentation", return_value=prs):
            docs = load_pptx_file(tmp_path / "deck.pptx")
        assert len(docs) == 1
        assert "Real content" in docs[0].page_content

    def test_metadata_page_is_0indexed_slide_number(self, tmp_path):
        prs = self._make_mock_pptx([["slide1"], ["slide2"], ["slide3"]])
        with patch("pptx.Presentation", return_value=prs):
            docs = load_pptx_file(tmp_path / "d.pptx")
        pages = [d.metadata["page"] for d in docs]
        assert pages == [0, 1, 2]

    def test_metadata_source_is_basename(self, tmp_path):
        prs = self._make_mock_pptx([["content"]])
        with patch("pptx.Presentation", return_value=prs):
            docs = load_pptx_file(tmp_path / "myslides.pptx")
        assert docs[0].metadata["source"] == "myslides.pptx"

    def test_all_empty_slides_returns_empty(self, tmp_path):
        prs = self._make_mock_pptx([[""], [""]])
        with patch("pptx.Presentation", return_value=prs):
            docs = load_pptx_file(tmp_path / "d.pptx")
        assert docs == []

    def test_import_error_returns_empty(self, tmp_path):
        with patch.dict(sys.modules, {"pptx": None}):
            docs = load_pptx_file(tmp_path / "d.pptx")
        assert docs == []


# ── load_file dispatch ─────────────────────────────────────────────────────────

class TestLoadFile:
    def test_dispatches_pdf(self, tmp_path):
        with patch("src.document_loader.load_pdf_file", return_value=[]) as mock_fn:
            load_file(tmp_path / "f.pdf")
            mock_fn.assert_called_once()

    def test_dispatches_txt(self, tmp_path):
        with patch("src.document_loader.load_txt_file", return_value=[]) as mock_fn:
            load_file(tmp_path / "f.txt")
            mock_fn.assert_called_once()

    def test_dispatches_csv(self, tmp_path):
        with patch("src.document_loader.load_csv_file", return_value=[]) as mock_fn:
            load_file(tmp_path / "f.csv")
            mock_fn.assert_called_once()

    def test_dispatches_docx(self, tmp_path):
        with patch("src.document_loader.load_docx_file", return_value=[]) as mock_fn:
            load_file(tmp_path / "f.docx")
            mock_fn.assert_called_once()

    def test_dispatches_pptx(self, tmp_path):
        with patch("src.document_loader.load_pptx_file", return_value=[]) as mock_fn:
            load_file(tmp_path / "f.pptx")
            mock_fn.assert_called_once()

    def test_unsupported_extension_returns_empty(self, tmp_path):
        docs = load_file(tmp_path / "f.zip")
        assert docs == []


# ── load_all_documents ─────────────────────────────────────────────────────────

class TestLoadAllDocuments:
    def test_non_existent_dir_created_and_returns_empty(self, tmp_path):
        """Phase 2 fix: missing directory is created; returns empty list."""
        new_dir = tmp_path / "new_kb"
        assert not new_dir.exists()
        docs = load_all_documents(new_dir)
        assert new_dir.exists()
        assert docs == []

    def test_empty_directory_returns_empty(self, tmp_path):
        docs = load_all_documents(tmp_path)
        assert docs == []

    def test_loads_txt_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
        (tmp_path / "b.txt").write_text("beta",  encoding="utf-8")
        docs = load_all_documents(tmp_path)
        assert len(docs) == 2

    def test_ignores_unsupported_extensions(self, tmp_path):
        """Files with unsupported extensions must be silently skipped."""
        (tmp_path / "a.txt").write_text("good", encoding="utf-8")
        (tmp_path / "b.zip").write_bytes(b"bad")
        (tmp_path / "c.exe").write_bytes(b"bad")
        docs = load_all_documents(tmp_path)
        assert len(docs) == 1

    def test_file_order_is_deterministic(self, tmp_path):
        """
        Phase 2 fix: files are sorted alphabetically before loading so the
        Document list order is reproducible across different filesystems.
        """
        (tmp_path / "z_last.txt").write_text("last",  encoding="utf-8")
        (tmp_path / "a_first.txt").write_text("first", encoding="utf-8")
        docs = load_all_documents(tmp_path)
        # a_first.txt comes before z_last.txt alphabetically
        assert "first" in docs[0].page_content
        assert "last"  in docs[1].page_content
