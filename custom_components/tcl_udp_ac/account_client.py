"""
TCL+ account/auth API client (cn.account.tcl.com).

Implements login and token refresh against the TCL+ account service so the
integration can obtain and renew cloud tokens itself, instead of requiring the
user to capture them manually.

All request parameters are RSA-encrypted using a public key fetched from
``/auth/common/publicKey`` (see :mod:`.tcl_crypto`). The encrypted base64 value
has ``=`` replaced with ``%3D`` while ``+`` and ``/`` are left raw, exactly as
the TCL+ app builds the query, so the URL is passed to aiohttp pre-encoded.

This client deliberately does not import Home Assistant, so it can be unit
tested in isolation.
"""

from __future__ import annotations

import json
import secrets
import string
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import aiohttp
from yarl import URL

from .const import (
    ACCOUNT_BTYPE_LOGIN,
    LOGGER,
)
from .tcl_crypto import (
    TclCryptoError,
    encrypt_param,
    load_public_key,
    md5_password,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# Fixed request headers that mark encrypted payloads (EncryptVersion 2.0).
_ENCRYPT_HEADERS = {"Encrypt": "true", "EncryptVersion": "2.0"}
_JSON_CONTENT_TYPE = "application/json;charset=utf-8"
_REQUEST_TIMEOUT = 15


class TclAccountError(Exception):
    """General account/auth API error."""


class TclAccountAuthError(TclAccountError):
    """Authentication failed (bad credentials, expired refresh token, etc.)."""


@dataclass(frozen=True)
class TclTokens:
    """Result of a successful login or refresh."""

    access_token: str
    refresh_token: str
    account_id: str | None = None


class AccountClient:
    """Client for the TCL+ account/auth API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str,
        app_id: str,
        app_secret: str,
        tenant_id: str,
    ) -> None:
        """Initialize the account client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._app_id = app_id
        self._app_secret = app_secret
        self._tenant_id = tenant_id
        self._public_key: object | None = None

    async def _ensure_public_key(self) -> object:
        if self._public_key is not None:
            return self._public_key
        url = f"{self._base_url}/auth/common/publicKey"
        try:
            async with self._session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
                text = await resp.text()
                if resp.status != HTTPStatus.OK:
                    msg = f"publicKey HTTP {resp.status}"
                    raise TclAccountError(msg)
        except (TimeoutError, aiohttp.ClientError) as exc:
            msg = "Failed to fetch TCL public key"
            raise TclAccountError(msg) from exc
        try:
            self._public_key = load_public_key(text)
        except TclCryptoError as exc:
            raise TclAccountError(str(exc)) from exc
        return self._public_key

    def _encrypt_query(self, params: Mapping[str, str], public_key: object) -> str:
        """
        Build a pre-encoded query string with RSA-encrypted values.

        Keys stay plain; each value is RSA-encrypted, base64-encoded, then ``=``
        is replaced with ``%3D`` (matching the app). ``+`` and ``/`` are left
        raw, so the caller must treat the URL as already encoded.
        """
        parts = []
        for key, value in params.items():
            enc = encrypt_param(value, public_key).replace("=", "%3D")
            parts.append(f"{key}={enc}")
        return "&".join(parts)

    async def _post_json_response(
        self, url_str: str, body: str | None
    ) -> dict[str, Any]:
        url = URL(url_str, encoded=True)
        headers = dict(_ENCRYPT_HEADERS)
        data = None
        if body is not None:
            headers["Content-Type"] = _JSON_CONTENT_TYPE
            data = body.encode("utf-8")
        try:
            async with self._session.post(
                url, data=data, headers=headers, timeout=_REQUEST_TIMEOUT
            ) as resp:
                text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as exc:
            msg = "Account request failed"
            raise TclAccountError(msg) from exc
        return self._parse_token_payload(text)

    async def _get_response(self, url_str: str, headers: Mapping[str, str]) -> str:
        url = URL(url_str, encoded=True)
        try:
            async with self._session.get(
                url, headers=headers, timeout=_REQUEST_TIMEOUT
            ) as resp:
                return await resp.text()
        except (TimeoutError, aiohttp.ClientError) as exc:
            msg = "Account request failed"
            raise TclAccountError(msg) from exc

    def _parse_token_payload(self, text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = "Account response was not JSON"
            raise TclAccountError(msg) from exc
        access = payload.get("accessToken")
        if not access:
            # The account API returns errorCode/msg on failure.
            err = payload.get("msg") or payload.get("errorCode") or "login failed"
            raise TclAccountAuthError(str(err))
        return payload

    @staticmethod
    def _tokens_from_payload(payload: Mapping[str, Any]) -> TclTokens:
        account_id = payload.get("accountId")
        return TclTokens(
            access_token=str(payload["accessToken"]),
            refresh_token=str(payload.get("refreshToken") or ""),
            account_id=str(account_id) if account_id is not None else None,
        )

    async def async_refresh(self, refresh_token: str, account_id: str) -> TclTokens:
        """Exchange a refresh token for a fresh access/refresh token pair."""
        public_key = await self._ensure_public_key()
        query = self._encrypt_query(
            {
                "accountId": account_id,
                "tenantId": self._tenant_id,
                "appId": self._app_id,
                "appSecret": self._app_secret,
            },
            public_key,
        )
        # Note: TCL spells the endpoint "refershToken".
        url = f"{self._base_url}/auth/auth/refershToken?{query}"
        # The refresh token travels as a plaintext header, not encrypted.
        text = await self._get_response(url, {"refreshToken": refresh_token})
        payload = self._parse_token_payload(text)
        LOGGER.debug("TCL token refresh succeeded")
        return self._tokens_from_payload(payload)

    async def async_login_password(self, username: str, password: str) -> TclTokens:
        """Log in with account + password (password sent as MD5 hash)."""
        public_key = await self._ensure_public_key()
        query = self._encrypt_query(
            {
                "tenantId": self._tenant_id,
                "reportState": _device_json(),
                "appId": self._app_id,
                "appSecret": self._app_secret,
            },
            public_key,
        )
        url = f"{self._base_url}/auth/auth/login?{query}"
        body_obj = {
            "username": username,
            "password": md5_password(password),
            "channel": "",
            "deviceId": "",
        }
        encrypted_body = encrypt_param(json.dumps(body_obj), public_key)
        payload = await self._post_json_response(url, encrypted_body)
        LOGGER.debug("TCL password login succeeded")
        return self._tokens_from_payload(payload)

    async def async_request_sms_code(self, mobile: str) -> None:
        """Request an SMS verification code for the given mobile number."""
        public_key = await self._ensure_public_key()
        timestamp = str(int(time.time() * 1000))
        nonce = "02" + _salt(8)
        query = self._encrypt_query(
            {
                "tenantId": self._tenant_id,
                "mobile": mobile,
                "timestamp": timestamp,
                "appId": self._app_id,
                "bType": ACCOUNT_BTYPE_LOGIN,
                "nonce": nonce,
                "appSecret": self._app_secret,
            },
            public_key,
        )
        url = f"{self._base_url}/captcha/captcha/new/smsCaptcha?{query}"
        text = await self._get_response(url, {})
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = "SMS response was not JSON"
            raise TclAccountError(msg) from exc
        if payload.get("status") != "SUCCESS":
            err = payload.get("msg") or payload.get("errorCode") or "sms request failed"
            raise TclAccountError(str(err))

    async def async_login_sms(self, mobile: str, code: str) -> TclTokens:
        """Log in with a mobile number and SMS verification code."""
        public_key = await self._ensure_public_key()
        query = self._encrypt_query(
            {
                "tenantId": self._tenant_id,
                "validCode": code,
                "username": mobile,
                "reportState": _device_json(),
                "appId": self._app_id,
                "bType": ACCOUNT_BTYPE_LOGIN,
                "deviceId": "",
                "appSecret": self._app_secret,
            },
            public_key,
        )
        url = f"{self._base_url}/auth/auth/quickLogin?{query}"
        payload = await self._post_json_response(url, None)
        LOGGER.debug("TCL SMS login succeeded")
        return self._tokens_from_payload(payload)


def _salt(length: int) -> str:
    """Return a lowercase alphanumeric salt (matches the app's nonce salt)."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _device_json() -> str:
    """Minimal device descriptor used for the reportState parameter."""
    return json.dumps({"platform": "android", "deviceId": ""})
