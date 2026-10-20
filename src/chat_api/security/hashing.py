"""Password hashing and verification utilities using bcrypt."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash plaintext password with a randomly generated bcrypt salt.

    Args:
        password: Plaintext password string.

    Returns:
        str: Bcrypt hashed password string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check plaintext password against bcrypt hash.

    Args:
        plain_password: Candidate plaintext password.
        hashed_password: Stored bcrypt hashed string.

    Returns:
        bool: True if password matches hash, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False
