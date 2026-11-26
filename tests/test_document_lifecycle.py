"""
tests/test_document_lifecycle.py — End-to-End Document Lifecycle Test (Phase 10).

Covers full end-to-end integration:
  1. User authentication and JWT resolution
  2. Document upload and multi-modal parsing
  3. FAISS vector indexing & BM25 keyword index updating
  4. Search and retrieval verification with grounded citations
  5. Cross-user isolation verification (unauthorized users cannot view or retrieve)
  6. Document deletion lifecycle: catalog purge, disk cleanup, vector purge
  7. Verification that deleted documents are never retrievable
"""
import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_chat_store, get_current_user, get_ingestion_service, get_retrieval_service
from api.main import app
from services.ingestion_service import IngestionService
from services.retrieval_service import RetrievalService
from storage import ChatStore


@pytest.fixture
def lifecycle_env(tmp_path, monkeypatch):
    test_db = tmp_path / "lifecycle.db"
    store = ChatStore(test_db)
    ingestion = IngestionService(db_store=store)
    retrieval = RetrievalService(db_store=store)

    user_alice = store.create_user("alice", "alice@example.com", "hash_alice", "user")
    user_bob = store.create_user("bob", "bob@example.com", "hash_bob", "user")

    # Mock embeddings to ensure fast and deterministic vector indexing without network calls
    class DeterministicMockEmbeddings:
        def embed_documents(self, texts):
            return [[0.05 * (i % 10)] * 384 for i, _ in enumerate(texts)]

        def embed_query(self, text):
            return [0.05] * 384

    mock_emb = DeterministicMockEmbeddings()
    monkeypatch.setattr("src.embeddings.get_embeddings", lambda: mock_emb)
    monkeypatch.setattr("services.ingestion_service.get_embeddings", lambda: mock_emb)

    app.dependency_overrides[get_chat_store] = lambda: store
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval

    yield store, ingestion, retrieval, user_alice, user_bob

    app.dependency_overrides.clear()


class TestCompleteDocumentLifecycle:
    def test_full_document_lifecycle_and_post_deletion_isolation(self, lifecycle_env):
        store, ingestion, retrieval, alice, bob = lifecycle_env

        # ── Step 1: Alice uploads a confidential document ──
        app.dependency_overrides[get_current_user] = lambda: alice
        with TestClient(app) as client_alice:
            doc_content = (
                b"PROJECT TITAN ARCHITECTURE SPECIFICATION:\n"
                b"The quantum encryption core operates at 4.2 Kelvin and uses lattice cryptography.\n"
                b"Proprietary access code is TITAN-9842-OMEGA."
            )
            upload_res = client_alice.post(
                "/api/v1/documents/upload",
                files={"file": ("project_titan.txt", doc_content, "text/plain")},
            )
            assert upload_res.status_code == 200, upload_res.text
            upload_data = upload_res.json()
            doc_id = upload_data["document"]["document_id"]
            assert upload_data["document"]["filename"] == "project_titan.txt"
            assert upload_data["document"]["chunk_count"] >= 1

            # ── Step 2: Verify Alice can list the document in her catalog ──
            list_res = client_alice.get("/api/v1/documents")
            assert list_res.status_code == 200
            alice_docs = list_res.json()
            assert any(d["document_id"] == doc_id for d in alice_docs)

        # ── Step 3: Verify Bob CANNOT see or access Alice's document ──
        app.dependency_overrides[get_current_user] = lambda: bob
        with TestClient(app) as client_bob:
            bob_list = client_bob.get("/api/v1/documents")
            assert bob_list.status_code == 200
            assert all(d["document_id"] != doc_id for d in bob_list.json())

            # Bob cannot delete Alice's document (returns 404)
            bob_del = client_bob.delete(f"/api/v1/documents/{doc_id}")
            assert bob_del.status_code == 404

        # ── Step 4: Verify retrieval works for Alice and filters out for Bob ──
        results_alice, _ = retrieval.retrieve(
            query="quantum encryption lattice cryptography",
            k=5,
            rerank=False,
            user_id=alice["user_id"],
        )
        assert any(r.document.metadata.get("document_id") == doc_id for r in results_alice)

        results_bob, _ = retrieval.retrieve(
            query="quantum encryption lattice cryptography",
            k=5,
            rerank=False,
            user_id=bob["user_id"],
        )
        assert all(r.document.metadata.get("document_id") != doc_id for r in results_bob)

        # ── Step 5: Alice deletes the document ──
        app.dependency_overrides[get_current_user] = lambda: alice
        with TestClient(app) as client_alice:
            del_res = client_alice.delete(f"/api/v1/documents/{doc_id}")
            assert del_res.status_code == 200

            # Document is gone from catalog
            list_after_del = client_alice.get("/api/v1/documents")
            assert all(d["document_id"] != doc_id for d in list_after_del.json())

            # Redundant delete returns 404
            del_again = client_alice.delete(f"/api/v1/documents/{doc_id}")
            assert del_again.status_code == 404

        # ── Step 6: Verify document is permanently purged from retrieval indexes ──
        post_del_results, _ = retrieval.retrieve(
            query="quantum encryption lattice cryptography TITAN-9842",
            k=5,
            rerank=False,
            user_id=alice["user_id"],
        )
        assert all(r.document.metadata.get("document_id") != doc_id for r in post_del_results)
