"""Tests for the TCL+ account/auth client request building and parsing."""

from __future__ import annotations

import asyncio
import base64
import json
import unittest

from tests.test_protocol_commands import load_integration_module
from tests.test_token_crypto import PUBLIC_KEY_B64


class FakeResponse:
    """Minimal async context manager mimicking aiohttp response."""

    def __init__(self, text: str, status: int = 200) -> None:
        self._text = text
        self.status = status

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def text(self) -> str:
        return self._text


class FakeSession:
    """Records GET/POST calls and returns queued responses."""

    def __init__(self) -> None:
        self.get_calls: list[dict] = []
        self.post_calls: list[dict] = []
        self._public_key_text = PUBLIC_KEY_B64
        self.token_response: str | None = None
        self.sms_response = '{"status":"SUCCESS","data":{"key":"x"}}'

    def get(self, url, headers=None, timeout=None):
        url_str = str(url)
        self.get_calls.append({"url": url_str, "headers": headers or {}})
        if "publicKey" in url_str:
            return FakeResponse(self._public_key_text)
        if "smsCaptcha" in url_str:
            return FakeResponse(self.sms_response)
        # refershToken
        return FakeResponse(self.token_response or "{}")

    def post(self, url, data=None, headers=None, timeout=None):
        self.post_calls.append(
            {"url": str(url), "data": data, "headers": headers or {}}
        )
        return FakeResponse(self.token_response or "{}")


# A login/refresh success payload (tokens truncated but valid JWT shape isn't
# required here — the client only reads accessToken/refreshToken/accountId).
TOKEN_PAYLOAD = json.dumps(
    {
        "accessToken": "access.jwt.sig",
        "refreshToken": "refresh.jwt.sig",
        "accountId": "121517358",
    }
)


def _client(session):
    mod = load_integration_module("account_client")
    return (
        mod,
        mod.AccountClient(
            session,
            base_url="https://cn.account.tcl.com",
            app_id="APPID",
            app_secret="APPSECRET",
            tenant_id="TCLPLUS",
        ),
    )


class AccountClientTest(unittest.TestCase):
    """Account client should encrypt params and parse token payloads."""

    def test_refresh_builds_encrypted_query_and_header(self) -> None:
        session = FakeSession()
        session.token_response = TOKEN_PAYLOAD
        mod, client = _client(session)

        tokens = asyncio.run(client.async_refresh("refresh.jwt.sig", "121517358"))

        self.assertEqual(tokens.access_token, "access.jwt.sig")
        self.assertEqual(tokens.refresh_token, "refresh.jwt.sig")
        self.assertEqual(tokens.account_id, "121517358")
        # publicKey fetched first, then refershToken GET.
        self.assertTrue(any("publicKey" in c["url"] for c in session.get_calls))
        refresh_call = next(c for c in session.get_calls if "refershToken" in c["url"])
        # Refresh token travels as a plaintext header.
        self.assertEqual(refresh_call["headers"]["refreshToken"], "refresh.jwt.sig")
        # Query keys are plain; values are RSA-encrypted (base64, '=' -> '%3D').
        self.assertIn("accountId=", refresh_call["url"])
        self.assertIn("appSecret=", refresh_call["url"])
        self.assertNotIn("appSecret=APPSECRET", refresh_call["url"])

    def test_login_password_sends_encrypted_body(self) -> None:
        session = FakeSession()
        session.token_response = TOKEN_PAYLOAD
        mod, client = _client(session)

        tokens = asyncio.run(client.async_login_password("user@x.com", "pw"))

        self.assertEqual(tokens.access_token, "access.jwt.sig")
        post = session.post_calls[0]
        self.assertIn("/auth/auth/login", post["url"])
        self.assertEqual(post["headers"]["Encrypt"], "true")
        self.assertEqual(post["headers"]["EncryptVersion"], "2.0")
        # Body is encrypted base64 bytes, not raw JSON.
        self.assertIsInstance(post["data"], bytes)
        self.assertNotIn(b"password", post["data"])
        # And it decodes as valid base64 (RSA ciphertext).
        base64.b64decode(post["data"])

    def test_login_failure_raises_auth_error(self) -> None:
        session = FakeSession()
        session.token_response = json.dumps(
            {"accessToken": None, "errorCode": "EC102401002", "msg": "bad password"}
        )
        mod, client = _client(session)

        with self.assertRaises(mod.TclAccountAuthError):
            asyncio.run(client.async_login_password("user", "wrong"))

    def test_sms_request_then_login(self) -> None:
        session = FakeSession()
        mod, client = _client(session)
        asyncio.run(client.async_request_sms_code("13800000000"))
        sms_call = next(c for c in session.get_calls if "smsCaptcha" in c["url"])
        # mobile/sign-style params present and encrypted.
        self.assertIn("mobile=", sms_call["url"])
        self.assertIn("nonce=", sms_call["url"])

        session.token_response = TOKEN_PAYLOAD
        tokens = asyncio.run(client.async_login_sms("13800000000", "123456"))
        self.assertEqual(tokens.access_token, "access.jwt.sig")
        quick = next(c for c in session.post_calls if "quickLogin" in c["url"])
        # quickLogin posts with no body (params are in the encrypted query).
        self.assertIsNone(quick["data"])


if __name__ == "__main__":
    unittest.main()
