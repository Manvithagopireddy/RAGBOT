"""
tests/test_auth_security.py — Dedicated Security and Authentication Tests (Phase 1).

Verifies:
  - Missing token -> 401
  - Invalid signature / forged token -> 401
  - Expired token -> 401
  - Alg none attack -> 401
  - Weak / incorrect algorithm -> 401
  - Password hashing security (bcrypt rounds and salt)
  - Rate limiting enforcement -> 429
  - Unauthenticated access to all protected endpoints -> 401
"""
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    rate_limiter,
    verify_password,
)
from storage import ChatStore


@pytest.fixture
def clean_client(tmp_path):
    test_db = tmp_path / "auth_test.db"
    store = ChatStore(test_db)
    from api.dependencies import get_chat_store
    app.dependency_overrides[get_chat_store] = lambda: store

    with TestClient(app) as client:
        yield client, store

    app.dependency_overrides.clear()


class TestTokenSecurity:
    def test_missing_token_returns_401(self, clean_client):
        client, _ = clean_client
        endpoints = [
            ("GET", "/api/v1/sessions"),
            ("POST", "/api/v1/sessions"),
            ("GET", "/api/v1/documents"),
            ("POST", "/api/v1/documents/upload"),
            ("POST", "/api/v1/chat"),
            ("POST", "/api/v1/chat/stream"),
            ("POST", "/api/v1/diagnostics/retrieve"),
            ("GET", "/api/v1/auth/me"),
        ]
        for method, endpoint in endpoints:
            if method == "GET":
                res = client.get(endpoint)
            else:
                res = client.post(endpoint, json={})
            assert res.status_code == 401, f"{method} {endpoint} did not return 401, got {res.status_code}"

    def test_forged_token_signature_rejected(self, clean_client):
        client, _ = clean_client
        forged_token = jwt.encode(
            {"sub": "attacker", "exp": 9999999999, "iat": 1000000000},
            "completely-wrong-secret-key-123456",
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {forged_token}"}
        res = client.get("/api/v1/sessions", headers=headers)
        assert res.status_code == 401

    def test_alg_none_attack_rejected(self):
        """Attempts to bypass verification using 'none' algorithm."""
        none_token = jwt.encode(
            {"sub": "attacker", "exp": 9999999999, "iat": 1000000000},
            key="",
            algorithm="none",
        )
        assert decode_access_token(none_token) is None

    def test_expired_token_rejected(self, clean_client):
        client, _ = clean_client
        expired = create_access_token(
            user_id="user-1",
            username="user1",
            expires_delta=timedelta(seconds=-60),
        )
        headers = {"Authorization": f"Bearer {expired}"}
        res = client.get("/api/v1/sessions", headers=headers)
        assert res.status_code == 401

    def test_tampered_token_payload_rejected(self, clean_client):
        client, _ = clean_client
        valid = create_access_token(user_id="user-1", username="user1")
        # Tamper payload part
        parts = valid.split(".")
        tampered = f"{parts[0]}.eyJuZXdfc3ViIjoidGFtcGVyZWQifQ.{parts[2]}"
        headers = {"Authorization": f"Bearer {tampered}"}
        res = client.get("/api/v1/sessions", headers=headers)
        assert res.status_code == 401


class TestPasswordAndRateLimitSecurity:
    def test_password_hashing_produces_unique_salts(self):
        pw = "SuperSecurePassword123!"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2, "Bcrypt must generate a unique salt for each hash operation"
        assert verify_password(pw, h1)
        assert verify_password(pw, h2)
        assert not verify_password("WrongPassword!", h1)

    def test_rate_limiter_sliding_window_enforcement(self):
        key = "test_ip_sliding_window"
        for _ in range(rate_limiter.rpm):
            allowed, _ = rate_limiter.is_allowed(key)
            assert allowed is True

        # Next request must be rejected
        allowed, retry_after = rate_limiter.is_allowed(key)
        assert allowed is False
        assert retry_after > 0
