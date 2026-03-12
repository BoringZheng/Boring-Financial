from backend.core.security import create_access_token, decode_token, get_password_hash, verify_password


def test_password_hash_roundtrip():
    hashed = get_password_hash("secret-123")
    assert verify_password("secret-123", hashed)


def test_access_token_contains_subject():
    token = create_access_token("42")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
