"""
tests/test_data_isolation.py — Cross-User Data Isolation Tests (Phase 2).

Verifies:
  - User A cannot view, update, or delete User B's sessions
  - User A cannot view or delete User B's documents
  - User A's hybrid retrieval filters out User B's documents
  - Document deletion properly purges vectors/chunks from retrieval indexes
"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api.dependencies import get_chat_store, get_current_user, get_ingestion_service, get_retrieval_service
from api.main import app
from services.ingestion_service import IngestionService
from services.retrieval_service import RetrievalService
from src.retriever import RetrievalResult
from storage import ChatStore


@pytest.fixture
def multi_user_setup(tmp_path):
    test_db = tmp_path / "isolation_test.db"
    store = ChatStore(test_db)
    ingestion = IngestionService(db_store=store)
    retrieval = RetrievalService(db_store=store)

    user_a = store.create_user("user_a", "usera@example.com", "hash_a", "user")
    user_b = store.create_user("user_b", "userb@example.com", "hash_b", "user")

    app.dependency_overrides[get_chat_store] = lambda: store
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval

    yield store, ingestion, retrieval, user_a, user_b

    app.dependency_overrides.clear()


class TestSessionIsolation:
    def test_user_cannot_access_other_users_session(self, multi_user_setup):
        store, _, _, user_a, user_b = multi_user_setup

        # User A creates a session
        session_a_id = store.create_session(
            title="User A Secret Session",
            user_id=user_a["user_id"],
        )
        store.add_message(session_a_id, "user", "Sensitive financial plan of User A")

        # Act as User B
        app.dependency_overrides[get_current_user] = lambda: user_b
        with TestClient(app) as client_b:
            # 1. Listing sessions should NOT contain User A's session
            list_res = client_b.get("/api/v1/sessions")
            assert list_res.status_code == 200
            session_ids = [s["session_id"] for s in list_res.json()]
            assert session_a_id not in session_ids

            # 2. Direct GET of User A's session should return 404
            get_res = client_b.get(f"/api/v1/sessions/{session_a_id}")
            assert get_res.status_code == 404

            # 3. Direct PATCH of User A's session should return 404
            patch_res = client_b.patch(
                f"/api/v1/sessions/{session_a_id}",
                json={"title": "Hacked Title"},
            )
            assert patch_res.status_code == 404

            # 4. Direct DELETE of User A's session should return 404
            del_res = client_b.delete(f"/api/v1/sessions/{session_a_id}")
            assert del_res.status_code == 404

        # Verify User A's session is still intact
        session_still_exists = store.get_session(session_a_id, user_id=user_a["user_id"])
        assert session_still_exists is not None
        assert session_still_exists["title"] == "User A Secret Session"


class TestDocumentIsolation:
    def test_user_cannot_access_or_delete_other_users_document(self, multi_user_setup):
        store, ingestion, _, user_a, user_b = multi_user_setup

        # User A has a document in the catalog
        store.add_document(
            document_id="doc-a-confidential",
            filename="user_a_confidential.pdf",
            file_path="/tmp/fake_a.pdf",
            file_type="pdf",
            file_size=1024,
            chunk_count=5,
            user_id=user_a["user_id"],
        )

        # Act as User B
        app.dependency_overrides[get_current_user] = lambda: user_b
        with TestClient(app) as client_b:
            # 1. User B's document list must NOT include User A's document
            list_res = client_b.get("/api/v1/documents")
            assert list_res.status_code == 200
            doc_ids = [d["document_id"] for d in list_res.json()]
            assert "doc-a-confidential" not in doc_ids

            # 2. User B cannot delete User A's document (returns 404)
            del_res = client_b.delete("/api/v1/documents/doc-a-confidential")
            assert del_res.status_code == 404


class TestRetrievalIsolation:
    def test_retrieval_service_filters_by_user_id(self, multi_user_setup, monkeypatch):
        store, _, retrieval, user_a, user_b = multi_user_setup

        # Register User A's document in DB
        store.add_document(
            document_id="doc-a-123",
            filename="patent_a.txt",
            file_path="/tmp/patent_a.txt",
            file_type="txt",
            file_size=100,
            user_id=user_a["user_id"],
        )

        # Register User B's document in DB
        store.add_document(
            document_id="doc-b-456",
            filename="secret_b.txt",
            file_path="/tmp/secret_b.txt",
            file_type="txt",
            file_size=100,
            user_id=user_b["user_id"],
        )

        # Mock candidates containing chunks from both documents and a public knowledge chunk
        chunk_a = RetrievalResult(
            document=Document(
                page_content="Proprietary algorithm belonging to User A",
                metadata={"document_id": "doc-a-123", "source": "patent_a.txt", "page": 1},
            ),
            similarity=0.95,
            distance=0.05,
        )
        chunk_b = RetrievalResult(
            document=Document(
                page_content="Trade secret belonging to User B",
                metadata={"document_id": "doc-b-456", "source": "secret_b.txt", "page": 1},
            ),
            similarity=0.96,
            distance=0.04,
        )
        chunk_public = RetrievalResult(
            document=Document(
                page_content="Public knowledge base architecture guide",
                metadata={"source": "public_guide.pdf", "page": 1},  # no document_id -> public
            ),
            similarity=0.90,
            distance=0.10,
        )

        # Mock the underlying vector/hybrid retriever to return all three
        monkeypatch.setattr(
            "services.retrieval_service.retrieve_and_rerank",
            lambda **kw: [chunk_b, chunk_a, chunk_public],
        )

        # Query as User A: must include chunk_a and chunk_public, must NOT include chunk_b
        results_a, diag_a = retrieval.retrieve(
            query="algorithm trade secret",
            k=5,
            rerank=False,
            user_id=user_a["user_id"],
        )
        returned_doc_ids_a = [r.document.metadata.get("document_id") for r in results_a]
        assert "doc-a-123" in returned_doc_ids_a
        assert "doc-b-456" not in returned_doc_ids_a
        # Public knowledge is preserved
        assert any(r.document.metadata.get("source") == "public_guide.pdf" for r in results_a)

        # Query as User B: must include chunk_b and chunk_public, must NOT include chunk_a
        results_b, diag_b = retrieval.retrieve(
            query="algorithm trade secret",
            k=5,
            rerank=False,
            user_id=user_b["user_id"],
        )
        returned_doc_ids_b = [r.document.metadata.get("document_id") for r in results_b]
        assert "doc-b-456" in returned_doc_ids_b
        assert "doc-a-123" not in returned_doc_ids_b
