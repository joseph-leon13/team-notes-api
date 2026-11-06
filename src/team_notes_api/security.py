"""Bearer-token generation and hashing.

This is a deliberately small stand-in for real authentication: tokens are random,
shown to the client once, and stored only as a sha256 digest. A high-entropy random
token does not need a slow password hash (there is nothing to brute-force from a
dictionary), and a deterministic digest lets authentication be one indexed lookup.
"""

import hashlib
import secrets


def generate_token() -> str:
    """Return a new random, URL-safe bearer token (256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the sha256 hexdigest under which ``token`` is stored and looked up."""
    return hashlib.sha256(token.encode()).hexdigest()
