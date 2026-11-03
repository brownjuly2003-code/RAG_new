"""Real bcrypt verification through the application, without passlib's backend."""

import bcrypt
import pytest


@pytest.mark.parametrize(
    "password,valid",
    [("valid password", True), ("x" * 73, False), ("é" * 37, False), ("wrong", False)],
)
def test_real_hash_login(client, monkeypatch, password, valid):
    monkeypatch.setenv("ADMIN_USERNAME", "owner")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", bcrypt.hashpw(b"valid password", bcrypt.gensalt(rounds=4)).decode()
    )
    response = client.post("/api/auth/login", json={"username": "owner", "password": password})
    assert response.status_code == (200 if valid else 401)
    if valid:
        assert response.json()["access_token"]
        assert client.cookies.get("access_token")


def test_malformed_hash_records_failed_login(client, monkeypatch):
    import api.app as api_app

    records = []

    async def audit(**kwargs):
        records.append(kwargs)

    monkeypatch.setattr(api_app, "log_audit", audit)
    monkeypatch.setenv("ADMIN_USERNAME", "owner")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "not-a-bcrypt-hash")
    response = client.post("/api/auth/login", json={"username": "owner", "password": "password"})
    assert response.status_code == 401
    assert records[-1]["action"] == "login_failed"
    assert records[-1]["detail"]["reason"] == "bad_password"


@pytest.mark.parametrize("suffix,status", [("", 200), ("y", 401)])
def test_72_byte_boundary_is_not_truncated(client, monkeypatch, suffix, status):
    prefix = "é" * 36
    monkeypatch.setenv("ADMIN_USERNAME", "owner")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", bcrypt.hashpw(prefix.encode(), bcrypt.gensalt(rounds=4)).decode()
    )
    response = client.post(
        "/api/auth/login", json={"username": "owner", "password": prefix + suffix}
    )
    assert response.status_code == status
