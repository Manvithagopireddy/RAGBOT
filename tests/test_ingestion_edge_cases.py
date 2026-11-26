"""
tests/test_ingestion_edge_cases.py — Ingestion Service & Document Route Edge Cases.

Increases coverage for:
  - IngestionService.reindex_document
  - IngestionService duplicate checksum handling
  - IngestionService delete_document with missing vector index
  - Document route reindex endpoint (/api/v1/documents/{document_id}/reindex)
  - Handling of non-existent documents and corrupt files
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_chat_store, get_current_user, get_ingestion_service
from api.main import app
from services.ingestion_service import IngestionService
from storage import ChatStore


@pytest.fixture
def ingestion_env(tmp_path, monkeypatch):
    test_db = tmp_path / "ingest_edge.db"
    store = ChatStore(test_db)
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch UPLOADS_DIR
    monkeypatch.setattr("services.ingestion_service.UPLOADS_DIR", uploads_dir)

    ingestion = IngestionService(db_store=store)
    user = store.create_user("ingestuser", "ingest@example.com", "hash_pw", "user")

    # Mock embeddings to be fast
    class MockEmbeddings:
        def embed_documents(self, texts):
            return [[0.1] * 384 for _ in texts]
        def embed_query(self, text):
            return [0.1] * 384

    monkeypatch.setattr("src.embeddings.get_embeddings", lambda: MockEmbeddings())
    monkeypatch.setattr("services.ingestion_service.get_embeddings", lambda: MockEmbeddings())

    app.dependency_overrides[get_chat_store] = lambda: store
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    app.dependency_overrides[get_current_user] = lambda: user

    yield store, ingestion, user, uploads_dir

    app.dependency_overrides.clear()


class TestIngestionEdgeCases:
    def test_duplicate_file_upload_returns_existing(self, ingestion_env):
        store, ingestion, user, _ = ingestion_env
        content = b"Exact duplicate content to test checksum match."

        # First ingestion
        res1 = ingestion.ingest_bytes(content, "dup_test.txt", user_id=user["user_id"])
        assert res1["status"] == "indexed"
        doc_id1 = res1["document_id"]

        # Second ingestion with identical content
        res2 = ingestion.ingest_bytes(content, "dup_test.txt", user_id=user["user_id"])
        assert res2["status"] == "indexed"
        assert res2["document_id"] == doc_id1
        assert res2["chunk_count"] == res1["chunk_count"]

    def test_reindex_existing_document(self, ingestion_env):
        store, ingestion, user, uploads_dir = ingestion_env
        content = b"Initial document content for reindexing."
        res = ingestion.ingest_bytes(content, "reindex_me.txt", user_id=user["user_id"])
        doc_id = res["document_id"]

        # Modify file on disk to simulate update
        file_path = Path(res["file_path"])
        file_path.write_bytes(b"Updated document content with additional text paragraphs.")

        # Reindex document
        reindexed = ingestion.reindex_document(doc_id, user_id=user["user_id"])
        assert reindexed["document_id"] == doc_id
        assert reindexed["status"] == "indexed"
        assert reindexed["chunk_count"] >= 1

    def test_reindex_nonexistent_document_raises_not_found(self, ingestion_env):
        _, ingestion, user, _ = ingestion_env
        with pytest.raises(ValueError, match="not found"):
            ingestion.reindex_document("nonexistent_doc_id", user_id=user["user_id"])

    def test_reindex_missing_physical_file_raises_not_found(self, ingestion_env):
        store, ingestion, user, _ = ingestion_env
        # Register a document whose physical file does not exist
        store.add_document(
            document_id="ghost_doc",
            filename="ghost.txt",
            file_path="/nonexistent/path/ghost.txt",
            file_type="txt",
            file_size=100,
            user_id=user["user_id"],
        )
        with pytest.raises(FileNotFoundError, match="not found on disk"):
            ingestion.reindex_document("ghost_doc", user_id=user["user_id"])

    def test_reindex_via_api_endpoint(self, ingestion_env):
        store, ingestion, user, _ = ingestion_env
        content = b"Content to test via API reindex route."
        res = ingestion.ingest_bytes(content, "api_reindex.txt", user_id=user["user_id"])
        doc_id = res["document_id"]

        with TestClient(app) as client:
            api_res = client.post(f"/api/v1/documents/{doc_id}/reindex")
            assert api_res.status_code == 200
            assert api_res.json()["document_id"] == doc_id

            # Nonexistent doc returns 400
            bad_res = client.post("/api/v1/documents/missing_doc_999/reindex")
            assert bad_res.status_code == 400

    def test_delete_document_when_index_is_none(self, ingestion_env):
        store, ingestion, user, _ = ingestion_env
        res = ingestion.ingest_bytes(b"Test content", "to_delete.txt", user_id=user["user_id"])
        doc_id = res["document_id"]

        # Explicitly set indexes to None on retrieval service
        from services.retrieval_service import retrieval_service
        retrieval_service.set_indexes(None, None)

        deleted = ingestion.delete_document(doc_id, user_id=user["user_id"])
        assert deleted is True
        assert store.get_document(doc_id) is None
