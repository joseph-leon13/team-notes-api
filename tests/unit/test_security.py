"""Unit tests for token generation and hashing."""

import hashlib

from team_notes_api.core.security import generate_token, hash_token


def test_tokens_are_random_and_high_entropy():
    tokens = {generate_token() for _ in range(50)}

    assert len(tokens) == 50
    assert all(len(token) >= 43 for token in tokens)  # 32 bytes, base64url


def test_hash_is_deterministic_sha256_hex():
    assert hash_token("abc") == hashlib.sha256(b"abc").hexdigest()
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64
