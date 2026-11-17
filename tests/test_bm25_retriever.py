"""
tests/test_bm25_retriever.py
Unit tests for the BM25Retriever and tokenization.
"""
from pathlib import Path

from langchain_core.documents import Document

from src.bm25_retriever import BM25Retriever, build_bm25_index, tokenize


class TestBM25Retriever:
    def test_tokenize(self):
        tokens = tokenize("LangChain & LangGraph are cyclical frameworks!")
        assert "langchain" in tokens
        assert "langgraph" in tokens
        assert "cyclical" in tokens
        assert "frameworks" in tokens
        assert "&" not in tokens

    def test_bm25_search_matches_relevant_chunk(self):
        docs = [
            Document(page_content="Vector databases store embeddings efficiently with FAISS.", metadata={"source": "db.pdf", "page": 0}),
            Document(page_content="Reinforcement learning uses reward signals for agents.", metadata={"source": "rl.pdf", "page": 0}),
            Document(page_content="Prompt engineering techniques include few-shot and chain of thought.", metadata={"source": "prompts.pdf", "page": 0}),
        ]
        retriever = BM25Retriever(docs)
        matches = retriever.retrieve("FAISS vector embeddings", k=2)
        assert len(matches) > 0
        top_doc, score, _ = matches[0]
        assert top_doc.metadata["source"] == "db.pdf"
        assert score > 0.0

    def test_bm25_retrieve_as_results(self):
        docs = [
            Document(page_content="CrewAI orchestrates multi-agent role-playing workflows.", metadata={"source": "crew.pdf", "page": 0}),
        ]
        retriever = BM25Retriever(docs)
        results = retriever.retrieve_as_results("CrewAI multi-agent", k=1)
        assert len(results) == 1
        assert results[0].source == "crew.pdf"
        assert results[0].similarity == 1.0  # normalized max score is 1.0

    def test_bm25_save_and_load(self, tmp_path: Path):
        docs = [
            Document(page_content="Sample document for serialization testing.", metadata={"source": "sample.pdf", "page": 0}),
        ]
        save_file = tmp_path / "bm25.pkl"
        build_bm25_index(docs, save_path=save_file)
        assert save_file.exists()

        loaded = BM25Retriever.load(save_file)
        assert loaded is not None
        assert len(loaded.documents) == 1
        matches = loaded.retrieve("serialization", k=1)
        assert len(matches) == 1
        assert matches[0][0].metadata["source"] == "sample.pdf"
