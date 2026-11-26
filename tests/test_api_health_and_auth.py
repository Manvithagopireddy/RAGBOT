"""
test_api_health_and_auth.py — Tests for Root, Health, and Authentication Endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from storage import ChatStore


@pytest.fixture
def client(tmp_path):
    """Provides a TestClient connected to an isolated temporary test database."""
    test_db = tmp_path / "test_chat.db"
    test_store = ChatStore(test_db)

    from api.dependencies import get_chat_store
    app.dependency_overrides[get_chat_store] = lambda: test_store

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestHealthAndRoot:
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RAGBOT API"
        assert data["status"] == "online"
        # Observability and security headers (Phases 1 & 14)
        assert "x-request-id" in response.headers
        assert "x-process-time" in response.headers
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"

    def test_health_endpoint(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        assert "faiss_ready" in data
        assert "x-request-id" in response.headers
        assert "x-process-time" in response.headers


class TestAuthEndpoints:
    def test_register_and_login_flow(self, client):
        # 1. Register new user
        reg_payload = {
            "username": "tester1",
            "email": "tester1@example.com",
            "password": "Password123!",
        }
        reg_res = client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        user_data = reg_res.json()
        assert user_data["username"] == "tester1"
        assert user_data["email"] == "tester1@example.com"
        assert "user_id" in user_data

        # 2. Prevent duplicate username
        dup_user = client.post("/api/v1/auth/register", json=reg_payload)
        assert dup_user.status_code == 400
        assert "already taken" in dup_user.json()["error"]

        # 3. Prevent duplicate email with different username
        dup_email = client.post("/api/v1/auth/register", json={
            "username": "tester2",
            "email": "tester1@example.com",
            "password": "Password123!",
        })
        assert dup_email.status_code == 400
        assert "already registered" in dup_email.json()["error"]

        # 4. Successful login
        login_res = client.post("/api/v1/auth/login", json={
            "username_or_email": "tester1",
            "password": "Password123!",
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["username"] == "tester1"

        token = token_data["access_token"]

        # 5. Get current profile with Bearer token
        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile["username"] == "tester1"
        assert profile["email"] == "tester1@example.com"

    def test_login_invalid_password(self, client):
        # Register user
        client.post("/api/v1/auth/register", json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "CorrectPassword123!",
        })

        # Attempt login with wrong password
        res = client.post("/api/v1/auth/login", json={
            "username_or_email": "bob",
            "password": "WrongPassword!",
        })
        assert res.status_code == 401
        assert "Incorrect username or password" in res.json()["error"]

    def test_me_without_token_returns_401(self, client):
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401


def test_patch_cors_preflight(client):
    response = client.options("/api/v1/sessions/example", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_untrusted_cors_origin(client):
    response = client.options("/api/v1/sessions/example", headers={
        "Origin": "https://untrusted.example",
        "Access-Control-Request-Method": "PATCH",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
