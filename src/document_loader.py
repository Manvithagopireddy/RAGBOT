"""
document_loader.py — Multi-format document loader: PDF, DOCX, TXT, CSV, PPTX.

Fixes applied (Phase 2):
  • Page numbering: all loaders now store page as a 0-indexed integer.
    Display conversion (+1) is performed once in retriever.py:RetrievalResult.page.
  • Metadata consistency: every Document always has both 'source' (basename)
    and 'page' (0-indexed int) keys — even when the format doesn't have pages.
  • Malformed-document handling: each loader wraps the read operation in a
    try/except and logs a descriptive error; it never raises to the caller.
  • CSV: empty-row guard prevents blank Documents from entering the index.
  • DOCX: table text is now extracted in addition to paragraph text.
  • PPTX: slides with no extractable text are silently skipped.
  • load_all_documents: sorted file list → deterministic chunk ordering across runs.
"""
import csv
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader  # pyright: ignore
from langchain_core.documents import Document  # pyright: ignore

from src.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".txt", ".csv", ".docx", ".pptx"}
)


# ── PDF ────────────────────────────────────────────────────────────────────────

def load_pdf_file(file_path: Path) -> List[Document]:
    """
    Loads a PDF and returns one Document per page.

    Metadata guaranteed on every document:
        source  — basename of the file (str)
        page    — 0-indexed page number (int)
    """
    logger.info(f"Loading PDF: {file_path.name}")
    try:
        loader = PyPDFLoader(str(file_path))
        documents = loader.load()
        # PyPDFLoader already sets page (0-indexed) in metadata.
        # Normalise: ensure 'source' is always the basename.
        for doc in documents:
            doc.metadata["source"] = file_path.name
            # Coerce page to int in case PyPDFLoader stores it differently
            doc.metadata["page"] = int(doc.metadata.get("page", 0))
        logger.info(f"Loaded {len(documents)} page(s) from '{file_path.name}'.")
        return documents
    except Exception as exc:
        logger.error(f"Failed to load PDF '{file_path.name}': {exc}")
        return []


# ── Plain text ─────────────────────────────────────────────────────────────────

def load_txt_file(file_path: Path) -> List[Document]:
    """
    Loads a plain-text file as a single Document.

    page is stored as 0 (0-indexed, displayed as page 1 elsewhere).
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            logger.warning(f"TXT file '{file_path.name}' is empty — skipped.")
            return []
        return [Document(
            page_content=text,
            metadata={"source": file_path.name, "page": 0},
        )]
    except Exception as exc:
        logger.error(f"Failed to load TXT '{file_path.name}': {exc}")
        return []


# ── CSV ────────────────────────────────────────────────────────────────────────

def load_csv_file(file_path: Path) -> List[Document]:
    """
    Loads a CSV file, converting each non-empty row to a Document.

    page is the 0-indexed row number.
    """
    try:
        docs: List[Document] = []
        with open(file_path, "r", encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            for row_idx, row in enumerate(reader):
                # Skip completely empty rows
                row_text = " | ".join(
                    f"{k}: {v}" for k, v in row.items() if v and str(v).strip()
                )
                if not row_text.strip():
                    continue
                docs.append(Document(
                    page_content=row_text,
                    metadata={"source": file_path.name, "page": row_idx},
                ))
        if not docs:
            logger.warning(f"CSV '{file_path.name}' contained no non-empty rows.")
        else:
            logger.info(f"Loaded {len(docs)} row(s) from CSV '{file_path.name}'.")
        return docs
    except Exception as exc:
        logger.error(f"Failed to load CSV '{file_path.name}': {exc}")
        return []


# ── DOCX ───────────────────────────────────────────────────────────────────────

def load_docx_file(file_path: Path) -> List[Document]:
    """
    Loads a Word document.  Extracts both paragraph text and table cell text.
    Returns a single Document (page=0); DOCX has no native page boundaries.
    """
    try:
        import docx  # python-docx
    except ImportError:
        logger.warning(
            "python-docx is not installed. "
            "Install it with: pip install python-docx"
        )
        return []

    try:
        word_doc = docx.Document(str(file_path))

        text_parts: List[str] = []

        # Paragraphs
        for para in word_doc.paragraphs:
            stripped = para.text.strip()
            if stripped:
                text_parts.append(stripped)

        # Tables (each cell on its own line)
        for table in word_doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    text_parts.append(" | ".join(row_cells))

        full_text = "\n".join(text_parts)
        if not full_text.strip():
            logger.warning(f"DOCX '{file_path.name}' contained no extractable text.")
            return []

        logger.info(f"Loaded DOCX '{file_path.name}' ({len(text_parts)} text block(s)).")
        return [Document(
            page_content=full_text,
            metadata={"source": file_path.name, "page": 0},
        )]
    except Exception as exc:
        logger.error(f"Failed to load DOCX '{file_path.name}': {exc}")
        return []


# ── PPTX ───────────────────────────────────────────────────────────────────────

def load_pptx_file(file_path: Path) -> List[Document]:
    """
    Loads a PowerPoint file.  Returns one Document per slide that contains text.
    page is 0-indexed slide number.
    """
    try:
        from pptx import Presentation  # python-pptx
    except ImportError:
        logger.warning(
            "python-pptx is not installed. "
            "Install it with: pip install python-pptx"
        )
        return []

    try:
        prs = Presentation(str(file_path))
        docs: List[Document] = []

        for slide_idx, slide in enumerate(prs.slides):
            text_parts: List[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text_parts.append(shape.text.strip())

            if not text_parts:
                continue  # Skip slides with no visible text

            docs.append(Document(
                page_content="\n".join(text_parts),
                metadata={"source": file_path.name, "page": slide_idx},
            ))

        if not docs:
            logger.warning(f"PPTX '{file_path.name}' contained no slides with text.")
        else:
            logger.info(f"Loaded {len(docs)} slide(s) from PPTX '{file_path.name}'.")
        return docs
    except Exception as exc:
        logger.error(f"Failed to load PPTX '{file_path.name}': {exc}")
        return []


# ── Dispatch ───────────────────────────────────────────────────────────────────

def load_file(file_path: Path) -> List[Document]:
    """
    Dispatches to the correct per-format loader based on file extension.
    Returns an empty list for unsupported types (never raises).
    """
    ext = file_path.suffix.lower()
    dispatch = {
        ".pdf":  load_pdf_file,
        ".txt":  load_txt_file,
        ".csv":  load_csv_file,
        ".docx": load_docx_file,
        ".pptx": load_pptx_file,
    }
    loader_fn = dispatch.get(ext)
    if loader_fn is None:
        logger.warning(f"Unsupported file extension '{ext}' for '{file_path.name}'.")
        return []
    return loader_fn(file_path)


def load_all_documents(directory_path: Path) -> List[Document]:
    """
    Scans a directory for all supported files and loads them.

    Files are sorted alphabetically before loading so the resulting
    Document list (and therefore FAISS chunk order) is deterministic
    across different OS / filesystem orderings.
    """
    logger.info(f"Scanning directory: {directory_path}")

    if not directory_path.exists():
        directory_path.mkdir(parents=True, exist_ok=True)
        logger.warning(f"Directory '{directory_path}' did not exist — created it.")
        return []

    files = sorted(
        f for f in directory_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.warning(f"No supported files found in '{directory_path}'.")
        return []

    logger.info(f"Found {len(files)} file(s) to load.")
    all_documents: List[Document] = []
    for f in files:
        docs = load_file(f)
        all_documents.extend(docs)
        if not docs:
            logger.warning(f"File '{f.name}' produced no documents.")

    logger.info(f"Total documents loaded: {len(all_documents)}.")
    return all_documents
