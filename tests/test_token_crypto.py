"""Tests for JWT decoding, RSA param encryption, and token lifetime logic."""

from __future__ import annotations

import base64
import json
import unittest

from tests.test_protocol_commands import load_integration_module

# Real TCL+ public key captured from /auth/common/publicKey (1024-bit RSA).
PUBLIC_KEY_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLuCAxtV1Omu216OFdY0p2ypPRLptl"
    "oLgMqvpmgkXD/SaB5RPx5oTzo5fdWjeYAx8N6YAe0DDJD5LsmNGhvVIiKOz2wYI17DQR"
    "K6aymvBuxioQzeAd5vI8RItTS7QpNh/ABH/B/3XhhVwnXn40MdDQxA3E2yfEk327Kqy4"
    "TqtscwIDAQAB"
)


def _make_jwt(exp: int, iat: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    body_raw = json.dumps({"exp": exp, "iat": iat}).encode()
    body = base64.urlsafe_b64encode(body_raw).decode().rstrip("=")
    return f"{header}.{body}.signature"


class CryptoTest(unittest.TestCase):
    """RSA encryption and JWT decode should match the TCL+ app behaviour."""

    def setUp(self) -> None:
        self.crypto = load_integration_module("tcl_crypto")

    def test_encrypt_param_matches_capture_shape(self) -> None:
        pub = self.crypto.load_public_key(PUBLIC_KEY_B64)
        enc = self.crypto.encrypt_param("TCLPLUS", pub)
        raw = base64.b64decode(enc)
        # 1024-bit RSA => 128-byte cipher blocks; short value => exactly one.
        self.assertEqual(len(raw), 128)
        self.assertEqual(len(enc), 172)

    def test_encrypt_param_chunks_long_values(self) -> None:
        pub = self.crypto.load_public_key(PUBLIC_KEY_B64)
        enc = self.crypto.encrypt_param("a" * 100, pub)
        raw = base64.b64decode(enc)
        # 100 bytes > 64-byte chunk => two RSA blocks.
        self.assertEqual(len(raw), 256)

    def test_invalid_public_key_raises(self) -> None:
        with self.assertRaises(self.crypto.TclCryptoError):
            self.crypto.load_public_key("not-base64-!!!")

    def test_md5_password(self) -> None:
        self.assertEqual(
            self.crypto.md5_password("test123"),
            "cc03e747a6afbbcbf8be7668acfebee5",
        )

    def test_decode_jwt_claims(self) -> None:
        token = _make_jwt(exp=1784136545, iat=1781544545)
        claims = self.crypto.decode_jwt_claims(token)
        self.assertEqual(claims["exp"], 1784136545)
        self.assertEqual(claims["iat"], 1781544545)

    def test_decode_jwt_garbage_returns_empty(self) -> None:
        self.assertEqual(self.crypto.decode_jwt_claims("garbage"), {})


class TokenStateTest(unittest.TestCase):
    """70%-of-lifetime refresh threshold and expiry checks."""

    def setUp(self) -> None:
        self.tok = load_integration_module("token_state")
        self.iat = 1781544545
        self.exp = self.iat + 30 * 86400  # 30-day access token
        self.token = _make_jwt(exp=self.exp, iat=self.iat)

    def test_no_refresh_early_in_life(self) -> None:
        self.assertFalse(self.tok.access_token_needs_refresh(self.token, self.iat + 10))

    def test_refresh_after_70_percent(self) -> None:
        past_70 = self.iat + (self.exp - self.iat) * 0.71
        self.assertTrue(self.tok.access_token_needs_refresh(self.token, past_70))

    def test_unparseable_token_needs_refresh(self) -> None:
        self.assertTrue(self.tok.access_token_needs_refresh("garbage", self.iat))

    def test_access_token_expiry(self) -> None:
        self.assertFalse(self.tok.access_token_expired(self.token, self.exp - 10))
        self.assertTrue(self.tok.access_token_expired(self.token, self.exp + 10))

    def test_refresh_token_expiry(self) -> None:
        self.assertFalse(self.tok.refresh_token_expired(self.token, self.exp - 10))
        self.assertTrue(self.tok.refresh_token_expired(self.token, self.exp + 10))
        self.assertTrue(self.tok.refresh_token_expired("", self.iat))


if __name__ == "__main__":
    unittest.main()
