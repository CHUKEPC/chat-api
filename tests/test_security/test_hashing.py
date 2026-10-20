"""Unit tests for password hashing and verification."""

from chat_api.security.hashing import hash_password, verify_password


def test_hash_password_generates_valid_bcrypt_hash() -> None:
    """Ensure generated password hash starts with standard bcrypt prefix."""
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    assert hashed.startswith("$2b$")
    assert hashed != plain


def test_verify_password_success() -> None:
    """Verify correct password matches hash."""
    plain = "ValidPassword99#"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong_password() -> None:
    """Verify incorrect password returns False."""
    plain = "ValidPassword99#"
    hashed = hash_password(plain)
    assert verify_password("WrongPassword!", hashed) is False


def test_verify_password_malformed_hash() -> None:
    """Verify malformed hash returns False gracefully without unhandled crash."""
    assert verify_password("plain", "not_a_valid_hash") is False
