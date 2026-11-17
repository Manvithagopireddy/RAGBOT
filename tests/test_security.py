"""
test_security.py — Unit Tests for Password Hashing, JWT Auth, Rate Limiter, and Sanitization.
"""
from datetime import timedelta

from src.security import (
    InMemoryRateLimiter,
    create_access_token,
    decode_access_token,
    hash_password,
    sanitize_html,
    verify_password,
)


class TestSecurityUtilities:
    def test_password_hashing_and_verification(self):
        plain = "SecretPassword123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_jwt_token_lifecycle(self):
        token = create_access_token(
            user_id="user-123",
            username="alice",
            role="admin",
            expires_delta=timedelta(minutes=30),
        )
        assert isinstance(token, str)

        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_jwt_expired_token(self):
        # Create token already expired
        expired_token = create_access_token(
            user_id="user-expired",
            username="bob",
            expires_delta=timedelta(seconds=-10),
        )
        payload = decode_access_token(expired_token)
        assert payload is None

    def test_jwt_invalid_token(self):
        payload = decode_access_token("this.is.not.a.valid.jwt.token")
        assert payload is None

    def test_sanitize_html(self):
        unsafe = '<script>alert("xss")</script><img src="x" onerror="alert(1)">'
        safe = sanitize_html(unsafe)
        assert "<script>" not in safe
        assert "&lt;script&gt;" in safe
        assert sanitize_html("") == ""

    def test_rate_limiter_allows_under_limit(self):
        limiter = InMemoryRateLimiter(requests_per_minute=5)
        client = "192.168.1.100"

        for _ in range(5):
            allowed, wait = limiter.is_allowed(client)
            assert allowed is True
            assert wait == 0

    def test_rate_limiter_blocks_over_limit(self):
        limiter = InMemoryRateLimiter(requests_per_minute=3)
        client = "192.168.1.101"

        # 3 requests allowed
        for _ in range(3):
            allowed, _ = limiter.is_allowed(client)
            assert allowed is True

        # 4th request blocked
        allowed, wait = limiter.is_allowed(client)
        assert allowed is False
        assert wait > 0
