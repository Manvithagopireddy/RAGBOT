"""
file_handler.py — Handles multi-format uploads (PDF, DOCX, TXT, CSV, PPTX).

Fixes applied (Phase 2):
  BUG-001  load_embedding_model → get_embeddings (broken import fixed)
  BUG-004  Path-traversal: filename sanitised with Path().name before write
  SEC-002  File size cap (MAX_UPLOAD_BYTES) + extension allowlist enforced
           before any bytes are read from the upload stream.
"""
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from src.logger import get_logger

logger = get_logger(__name__)

# Allowed extensions (lower-case, with leading dot)
SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".txt", ".csv", ".docx", ".pptx"}

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

# Human-readable labels for the UI
_EXT_ICONS: dict[str, str] = {
    ".pdf":  "📄",
    ".txt":  "📝",
    ".csv":  "📊",
    ".docx": "📘",
    ".pptx": "📑",
}


# ── Validation helpers ─────────────────────────────────────────────────────────

def verify_magic_bytes(data: bytes, ext: str) -> Tuple[bool, str]:
    """
    Verifies that file header bytes match the expected signature for the extension.
    Prevents executable or malicious binary masquerading.
    """
    if len(data) < 4:
        return False, "File is too small to determine content type."

    # Check for known dangerous executable headers regardless of declared extension
    dangerous_signatures = [
        (b"MZ", "Windows executable/DLL (PE)"),
        (b"\x7fELF", "Linux executable (ELF)"),
        (b"\xca\xfe\xba\xbe", "Compiled binary (Mach-O / Java Class)"),
        (b"\xfe\xed\xfa\xce", "Mach-O 32-bit binary"),
        (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit binary"),
    ]
    for sig, desc in dangerous_signatures:
        if data.startswith(sig):
            return False, f"Dangerous binary signature detected: {desc}. Upload rejected."

    ext = ext.lower()
    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            return False, "Invalid PDF header: signature does not match '%PDF'."
    elif ext in (".docx", ".pptx"):
        # Office Open XML files are zip containers starting with PK\x03\x04
        if not data.startswith(b"PK\x03\x04"):
            return False, f"Invalid Office document header: expected Zip-based container for {ext}."
    elif ext in (".txt", ".csv"):
        # Text/CSV files must not contain binary NUL bytes
        sample = data[:1024]
        if b"\x00" in sample:
            return False, f"Binary null byte detected in text document ({ext}). Upload rejected."

    return True, ""


def _safe_filename(raw_name: str) -> str:
    """
    Strip directory components and remove characters that could be dangerous
    on any OS.  Returns a sanitised basename with only alphanumeric chars,
    dots, hyphens, and underscores.
    """
    # 1. Keep only the final component (prevents path traversal)
    basename = Path(raw_name).name
    # 2. Replace every dangerous character with an underscore
    safe = re.sub(r"[^\w.\-]", "_", basename)
    # 3. Guard against empty result
    return safe or "upload"


def validate_upload(
    uploaded_file,
) -> Tuple[bool, str]:
    """
    Validates an uploaded file object before any bytes are written to disk.

    Returns:
        (True, "")          when the file passes all checks.
        (False, reason_str) when it fails, with a human-readable reason.
    """
    name: str = getattr(uploaded_file, "name", "") or ""
    ext = Path(name).suffix.lower()

    # 1. Extension allowlist
    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 2. File size — read once into a buffer and check length
    try:
        data: bytes = uploaded_file.getvalue()
    except Exception as exc:
        return False, f"Could not read file content: {exc}"

    if len(data) == 0:
        return False, "File is empty."

    if len(data) > MAX_UPLOAD_BYTES:
        mb = len(data) / (1024 * 1024)
        return False, (
            f"File is too large ({mb:.1f} MB). "
            f"Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    # 3. Magic byte signature verification
    valid_sig, sig_err = verify_magic_bytes(data, ext)
    if not valid_sig:
        return False, sig_err

    return True, ""


# ── Core indexing ──────────────────────────────────────────────────────────────

def index_uploaded_file(uploaded_file, global_db) -> Optional[object]:
    """
    Validates, saves, and indexes a Streamlit UploadedFile into the FAISS store.

    Steps:
      1. Validate extension and file size (early-exit on failure).
      2. Sanitise filename to prevent path traversal.
      3. Write bytes to UPLOADS_DIR with a unique prefix.
      4. Load → split → embed → build per-upload FAISS index.
      5. Merge into global_db (or return the per-upload index if global_db is None).

    Returns the updated FAISS db on success, global_db unchanged on failure.
    """
    # ── Imports kept inside function to avoid circular imports at module level
    from langchain_community.vectorstores import FAISS  # pyright: ignore

    from config.settings import UPLOADS_DIR
    from src.document_loader import load_file

    # FIX BUG-001: use the correct function name from src/embeddings.py
    from src.embeddings import get_embeddings  # was: load_embedding_model
    from src.text_splitter import split_documents

    # ── Step 1: Validate before touching the filesystem ───────────────────────
    ok, reason = validate_upload(uploaded_file)
    if not ok:
        logger.warning(f"Upload rejected ({uploaded_file.name}): {reason}")
        return global_db

    # ── Step 2: Sanitise filename (FIX BUG-004 / SEC-002 path-traversal) ─────
    safe_name = _safe_filename(uploaded_file.name)

    # Unique prefix prevents silent overwrites of previous uploads with same name
    unique_id = uuid.uuid4().hex[:8]
    dest_filename = f"upload_{unique_id}_{safe_name}"

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = UPLOADS_DIR / dest_filename

    # ── Step 3: Write to disk ─────────────────────────────────────────────────
    try:
        raw_bytes: bytes = uploaded_file.getvalue()
        dest_path.write_bytes(raw_bytes)
        logger.info(f"Saved uploaded file → {dest_path} ({len(raw_bytes):,} bytes)")
    except Exception as write_err:
        logger.error(f"Failed to write upload to disk: {write_err}")
        return global_db

    # ── Step 4: Load, split, embed ────────────────────────────────────────────
    try:
        documents = load_file(dest_path)
    except Exception as load_err:
        logger.error(f"Document loader raised an exception for {safe_name}: {load_err}")
        _safe_delete(dest_path)
        return global_db

    if not documents:
        logger.warning(f"No extractable text found in '{safe_name}'. File skipped.")
        _safe_delete(dest_path)
        return global_db

    # Inject the original (safe) filename into every chunk's metadata so
    # citations display the user's intended filename, not the UUID-prefixed one.
    for doc in documents:
        doc.metadata["source"] = safe_name

    chunks = split_documents(documents)

    if not chunks:
        logger.warning(f"Text splitting produced no chunks for '{safe_name}'.")
        _safe_delete(dest_path)
        return global_db

    logger.info(f"Generated {len(chunks)} chunks from '{safe_name}'.")

    try:
        embeddings = get_embeddings()   # FIX BUG-001: was load_embedding_model()
        upload_db = FAISS.from_documents(chunks, embeddings)
    except Exception as embed_err:
        logger.error(f"Embedding/FAISS build failed for '{safe_name}': {embed_err}")
        _safe_delete(dest_path)
        return global_db

    # ── Step 5: Merge ─────────────────────────────────────────────────────────
    if global_db is not None:
        try:
            global_db.merge_from(upload_db)
            logger.info(f"Merged '{safe_name}' into global FAISS store.")
            return global_db
        except Exception as merge_err:
            logger.warning(
                f"FAISS merge failed for '{safe_name}', returning upload-only store: {merge_err}"
            )
            return upload_db
    else:
        logger.info(f"No global DB — returning upload-only store for '{safe_name}'.")
        return upload_db


def _safe_delete(path: Path) -> None:
    """Silently removes a file if it exists; never raises."""
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


# ── UI helpers ────────────────────────────────────────────────────────────────

def get_file_size_label(uploaded_file) -> str:
    """Returns a human-readable file size string."""
    try:
        size = len(uploaded_file.getvalue())
    except Exception:
        size = 0
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def get_file_icon(filename: str) -> str:
    """Returns an emoji icon for the given file type."""
    ext = Path(filename).suffix.lower()
    return _EXT_ICONS.get(ext, "📎")
