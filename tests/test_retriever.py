from langchain_core.documents import Document
from src.retriever import format_retrieved_context


def test_format_retrieved_context_empty():
    """Tests formatting when no chunks were retrieved."""
    context_text, citations, avg_confidence = format_retrieved_context([])
    assert context_text == ""
    assert citations == []
    assert avg_confidence == 0.0


def test_format_retrieved_context_with_docs():
    """Tests formatting retrieved documents into prompt context and citation objects."""
    docs = [
        (
            Document(page_content="Vector databases store embeddings efficiently.", metadata={"source": "vector_db.pdf", "page": 0}),
            0.85
        ),
        (
            Document(page_content="Cosine similarity is used to calculate proximity.", metadata={"source": "math.pdf", "page": 2}),
            0.65
        )
    ]

    context_text, citations, avg_confidence = format_retrieved_context(docs)

    # 1. Check prompt context string
    assert "Document Source: vector_db.pdf (Page 1)" in context_text
    assert "Vector databases store embeddings efficiently." in context_text
    assert "Document Source: math.pdf (Page 3)" in context_text

    # 2. Check citations structure
    assert len(citations) == 2
    assert citations[0]["id"] == 1
    assert citations[0]["source"] == "vector_db.pdf"
    assert citations[0]["page"] == 1
    assert citations[0]["score"] == 0.85

    assert citations[1]["id"] == 2
    assert citations[1]["source"] == "math.pdf"
    assert citations[1]["page"] == 3
    assert citations[1]["score"] == 0.65

    # 3. Check average confidence
    assert avg_confidence == (0.85 + 0.65) / 2
