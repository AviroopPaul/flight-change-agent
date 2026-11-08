import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from gcp import vertex_credentials


def fake_key() -> str:
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return json.dumps({
        "type": "service_account", "project_id": "p", "private_key_id": "k", "private_key": pem,
        "client_email": "llm@p.iam.gserviceaccount.com", "client_id": "1",
        "token_uri": "https://oauth2.googleapis.com/token",
    })


def test_no_key_json_falls_back_to_adc(monkeypatch):
    monkeypatch.delenv("GOOGLE_CREDENTIALS_JSON", raising=False)
    assert vertex_credentials() is None


def test_key_json_gives_scoped_service_account(monkeypatch):
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", fake_key())
    creds = vertex_credentials()
    assert creds.service_account_email == "llm@p.iam.gserviceaccount.com"
    assert "https://www.googleapis.com/auth/cloud-platform" in creds.scopes
