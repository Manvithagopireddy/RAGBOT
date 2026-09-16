from langchain_core.documents import Document
from src.text_splitter import split_documents
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP


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


def test_split_large_document():
    """Tests that large texts are divided into multiple chunks respecting CHUNK_SIZE."""
    long_text = "Artificial intelligence and large language models are transforming computing. " * 30
    doc = Document(page_content=long_text, metadata={"source": "long_doc.pdf"})
    chunks = split_documents([doc])

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.page_content) <= CHUNK_SIZE + 50
        assert chunk.metadata["source"] == "long_doc.pdf"


def test_split_empty_documents():
    """Tests that empty document lists return an empty list without raising errors."""
    chunks = split_documents([])
    assert chunks == []
