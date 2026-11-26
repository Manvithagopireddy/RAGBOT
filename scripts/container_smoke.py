"""HTTP smoke checks against a running disposable RAGBOT stack (no LLM key required)."""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = os.environ.get("RAGBOT_SMOKE_URL", "http://127.0.0.1:18080")


def request(path, method="GET", payload=None, token=None, expected=200):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=30)  # nosec B310 - fixed local CI URL
    except HTTPError as exc:
        response = exc
    with response:
        assert response.status == expected, (path, response.status, expected)
        raw = response.read()
        return json.loads(raw) if raw else None


def create_user():
    name = "smoke_" + uuid4().hex[:12]
    password = uuid4().hex + "Aa1!"
    request("/api/v1/auth/register", "POST", {
        "username": name, "email": name + "@example.com", "password": password,
    }, expected=201)
    return request("/api/v1/auth/login", "POST", {
        "username_or_email": name, "password": password,
    })["access_token"]


def main():
    assert request("/api/v1/health")["status"] == "ok"
    request("/api/v1/sessions", expected=401)
    owner, other = create_user(), create_user()
    session = request("/api/v1/sessions", "POST", {"title": "Smoke test"}, owner, 201)
    path = "/api/v1/sessions/" + session["session_id"]
    assert request(path, token=owner)["title"] == "Smoke test"
    assert request(path, "PATCH", {"title": "Renamed"}, owner)["title"] == "Renamed"
    request(path, token=other, expected=404)
    request(path, "PATCH", {"title": "Denied"}, other, 404)
    request(path, "DELETE", token=other, expected=404)
    request("/api/v1/documents", token=owner)
    request(path, "DELETE", token=owner)
    request(path, token=owner, expected=404)
    print("Container HTTP smoke checks passed: health, auth, sessions, ownership and document listing.")


if __name__ == "__main__":
    main()
