"""
test_api_sessions_and_docs.py — Tests for Session CRUD and Document Upload/Listing Endpoints.
Includes auth enforcement verification (Phase 1).
"""
import pytest
from fastapi.testclient import TestClient

from api.dependencies import (
    get_chat_store,
    get_current_user,
    get_ingestion_service,
)
from api.main import app
from services.ingestion_service import IngestionService
from storage import ChatStore


@pytest.fixture
def client_and_store(tmp_path):
    test_db = tmp_path / "test_sessions.db"
    test_store = ChatStore(test_db)
    test_ingestion = IngestionService(db_store=test_store)

    # Seed authenticated user in test DB to satisfy FK constraints
    test_user = test_store.create_user(
        username="sessionuser",
        email="sessionuser@example.com",
        hashed_password="mock_hashed_pw",
        role="user",
    )

    app.dependency_overrides[get_chat_store] = lambda: test_store
    app.dependency_overrides[get_ingestion_service] = lambda: test_ingestion
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as test_client:
        yield test_client, test_store

    app.dependency_overrides.clear()


class TestSessionEndpoints:
    def test_session_crud_lifecycle(self, client_and_store):
        client, store = client_and_store

        # 1. Create session
        create_res = client.post("/api/v1/sessions", json={
            "title": "Machine Learning Chat",
            "model": "gemini-2.5-flash",
            "temperature": 0.5,
            "retriever_k": 3,
        })
        assert create_res.status_code == 201
        sess = create_res.json()
        session_id = sess["session_id"]
        assert sess["title"] == "Machine Learning Chat"
        assert sess["temperature"] == 0.5

        # 2. List sessions
        list_res = client.get("/api/v1/sessions")
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert len(sessions) >= 1
        assert any(s["session_id"] == session_id for s in sessions)

        # 3. Get session details (with messages)
        get_res = client.get(f"/api/v1/sessions/{session_id}")
        assert get_res.status_code == 200
        details = get_res.json()
        assert details["session_id"] == session_id
        assert "messages" in details
        assert isinstance(details["messages"], list)

        # 4. Patch/update session
        patch_res = client.patch(f"/api/v1/sessions/{session_id}", json={
            "title": "Updated ML Chat",
            "temperature": 0.2,
        })
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["title"] == "Updated ML Chat"
        assert updated["temperature"] == 0.2

        # 5. Delete session
        del_res = client.delete(f"/api/v1/sessions/{session_id}")
        assert del_res.status_code == 200

        # Verify not found
        get_again = client.get(f"/api/v1/sessions/{session_id}")
        assert get_again.status_code == 404

    def test_unauthenticated_sessions_return_401(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            assert client.get("/api/v1/sessions").status_code == 401
            assert client.post("/api/v1/sessions", json={"title": "Test"}).status_code == 401


class TestDocumentEndpoints:
    def test_upload_invalid_extension(self, client_and_store):
        client, _ = client_and_store
        file_bytes = b"bad executable content"
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("malware.exe", file_bytes, "application/octet-stream")},
        )
        assert res.status_code == 400
        assert "Unsupported file type" in res.json()["error"]

    def test_upload_empty_file(self, client_and_store):
        client, _ = client_and_store
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert res.status_code == 400
        assert "empty" in res.json()["error"]

    def test_upload_valid_txt_file(self, client_and_store, monkeypatch):
        client, store = client_and_store

        # Mock embeddings to make upload fast and offline
        class DummyEmbeddings:
            def embed_documents(self, texts):
                return [[0.1] * 384 for _ in texts]
            def embed_query(self, text):
                return [0.1] * 384

        monkeypatch.setattr("src.embeddings.get_embeddings", lambda: DummyEmbeddings())
        monkeypatch.setattr("services.ingestion_service.get_embeddings", lambda: DummyEmbeddings())

        content = b"This is a test document explaining Retrieval Augmented Generation architecture."
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test_doc.txt", content, "text/plain")},
        )
        assert res.status_code == 200
        data = res.json()
        assert "document" in data
        doc = data["document"]
        assert doc["filename"] == "test_doc.txt"
        assert doc["file_type"] == "txt"
        assert doc["chunk_count"] >= 1
        doc_id = doc["document_id"]

        # List documents
        list_res = client.get("/api/v1/documents")
        assert list_res.status_code == 200
        docs = list_res.json()
        assert any(d["document_id"] == doc_id for d in docs)

        # Delete document
        del_res = client.delete(f"/api/v1/documents/{doc_id}")
        assert del_res.status_code == 200

    def test_unauthenticated_documents_return_401(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            assert client.get("/api/v1/documents").status_code == 401
            assert client.post("/api/v1/documents/upload").status_code == 401


def test_zero_temperature_is_preserved(client_and_store):
    client, _ = client_and_store
    response = client.post("/api/v1/sessions", json={"title": "Deterministic", "temperature": 0.0})
    assert response.status_code == 201
    assert response.json()["temperature"] == 0.0
    session_id = response.json()["session_id"]
    updated = client.patch(f"/api/v1/sessions/{session_id}", json={"temperature": 0.0})
    assert updated.status_code == 200
    assert updated.json()["temperature"] == 0.0
