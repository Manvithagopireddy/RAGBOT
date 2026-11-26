"""
tests/test_text_splitter.py — Unit tests for token-aware and character-based chunking.
"""
from langchain_core.documents import Document

from src.text_splitter import get_text_splitter, split_documents


def test_split_documents_preserves_metadata():
    """Tests that splitting maintains the document source and metadata."""
    doc = Document(
        page_content="Sample text content for retrieval testing.",
        metadata={"source": "guide.pdf", "page": 1}
    )
    chunks = split_documents([doc])
    assert len(chunks) == 1
    assert chunks[0].page_content == "Sample text content for retrieval testing."
    assert chunks[0].metadata["source"] == "guide.pdf"
    assert chunks[0].metadata["page"] == 1
    assert "chunk_index" in chunks[0].metadata
    assert "chunk_id" in chunks[0].metadata


def test_split_large_document():
    """Tests that large texts are divided into multiple chunks respecting CHUNK_SIZE."""
    long_text = "Artificial intelligence and large language models are transforming computing. " * 30
    doc = Document(page_content=long_text, metadata={"source": "long_doc.pdf"})
    chunks = split_documents([doc])

    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert len(chunk.page_content) > 0
        assert chunk.metadata["source"] == "long_doc.pdf"
        assert chunk.metadata["chunk_index"] == i


def test_split_empty_documents():
    """Tests that empty document lists return an empty list without raising errors."""
    chunks = split_documents([])
    assert chunks == []


def test_get_text_splitter_token_method():
    """Tests token-aware splitter factory."""
    splitter = get_text_splitter(method="token", chunk_size=200, chunk_overlap=20)
    assert splitter is not None
    chunks = splitter.split_text("Testing token based text splitting with tiktoken encoder.")
    assert len(chunks) >= 1


def test_get_text_splitter_character_method():
    """Tests character-based splitter factory."""
    splitter = get_text_splitter(method="character", chunk_size=100, chunk_overlap=10)
    assert splitter is not None
    chunks = splitter.split_text("Testing character based text splitting with length function. " * 10)
    assert len(chunks) > 1


def test_split_documents_with_custom_method():
    """Tests split_documents explicitly using character method."""
    doc = Document(page_content="Quick test text.", metadata={"source": "test.txt"})
    chunks = split_documents([doc], method="character", chunk_size=50, chunk_overlap=5)
    assert len(chunks) == 1
    assert chunks[0].metadata["chunk_id"] == "test.txt::p0::c0"
