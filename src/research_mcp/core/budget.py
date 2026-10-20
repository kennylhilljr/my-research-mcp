"""Bound serialized envelopes and authenticate opaque pagination cursors."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel, JsonValue, ValidationError

from research_mcp.core.envelope import ToolResult
from research_mcp.core.errors import ErrorCode, ToolError

TRUNCATION_MARKER = "[truncated]"
_PROTECTED = {
    "next_cursor",
    "cursor",
    "source",
    "untrusted",
    "source_status",
    "statuses",
    "warnings",
}


def _containers(value: Any) -> Iterator[list[Any]]:
    if isinstance(value, list):
        yield value
        for item in value:
            yield from _containers(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in _PROTECTED:
                yield from _containers(item)


def _texts(value: Any) -> Iterator[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PROTECTED:
                continue
            if isinstance(item, str) and len(item) > len(TRUNCATION_MARKER):
                yield value, key
            else:
                yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)


def _size(value: BaseModel) -> int:
    return len(value.model_dump_json().encode("utf-8"))


def _raw_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _longest[T](
    payload: dict[str, Any],
    set_length: Callable[[int], None],
    high: int,
    limit_bytes: int,
    fits: Callable[[], ToolResult[T] | None],
) -> ToolResult[T] | None:
    # Size grows with length but schema validity need not (min_length), so the
    # binary search looks at bytes only and validation happens on the way down.
    low, longest = 0, -1
    while low <= high:
        middle = (low + high) // 2
        set_length(middle)
        if _raw_size(payload) <= limit_bytes:
            longest, low = middle, middle + 1
        else:
            high = middle - 1
    for length in range(longest, -1, -1):
        set_length(length)
        value = fits()
        if value is not None:
            return value
    return None


def _trim_lists[T](
    payload: dict[str, Any],
    limit_bytes: int,
    candidate: Callable[[], ToolResult[T] | None],
    fits: Callable[[], ToolResult[T] | None],
) -> ToolResult[T] | None:
    for items in _containers(payload["data"]):
        original = items[:]

        def set_length(
            length: int, items: list[Any] = items, original: list[Any] = original
        ) -> None:
            items[:] = original[:length]

        value = _longest(payload, set_length, len(original), limit_bytes, fits)
        if value is not None:
            return value
        items.clear()
        if candidate() is None:
            items[:] = original
    return None


def _trim_text[T](
    payload: dict[str, Any],
    limit_bytes: int,
    candidate: Callable[[], ToolResult[T] | None],
    fits: Callable[[], ToolResult[T] | None],
) -> ToolResult[T] | None:
    for parent, key in _texts(payload):
        # Metadata strings are immutable; only data text is eligible.
        if parent is payload and key != "data":
            continue
        original_text = parent[key]

        def set_length(
            length: int, parent: dict[str, Any] = parent, key: str = key, text: str = original_text
        ) -> None:
            parent[key] = text[:length] + TRUNCATION_MARKER

        high = len(original_text) - len(TRUNCATION_MARKER)
        value = _longest(payload, set_length, high, limit_bytes, fits)
        if value is not None:
            return value
        parent[key] = TRUNCATION_MARKER
        if candidate() is None:
            parent[key] = original_text
    return None


def fit[T](result: ToolResult[T], limit_bytes: int = 64 * 1024) -> ToolResult[T]:
    """Return a validated copy; fail if mandatory metadata cannot fit.

    Data lists lose trailing items before text is shortened. Source statuses,
    source labels and cursors are never rewritten. The input is not mutated.
    """
    if isinstance(limit_bytes, bool) or not isinstance(limit_bytes, int) or limit_bytes < 1:
        raise ToolError(ErrorCode.INVALID_ARGUMENT, "Budget must be a positive byte count")
    if _size(result) <= limit_bytes:
        return result.model_copy(deep=True)
    payload = result.model_dump(mode="json")
    payload["truncated"] = True

    def candidate() -> ToolResult[T] | None:
        try:
            return type(result).model_validate(payload).model_copy(deep=True)
        except ValidationError:
            return None

    def fits() -> ToolResult[T] | None:
        value = candidate()
        return value if value is not None and _size(value) <= limit_bytes else None

    for trim in (_trim_lists, _trim_text):
        value = trim(payload, limit_bytes, candidate, fits)
        if value is not None:
            return value
    payload["warnings"] = []
    value = fits()
    if value is not None:
        return value
    raise ToolError(ErrorCode.TOO_LARGE, "Required result fields exceed the response budget")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _b64encode(decoded) != value:
        raise ValueError("Noncanonical base64url")
    return decoded


def encode_cursor(payload: dict[str, JsonValue], key: bytes) -> str:
    """Sign a JSON object using the caller's daemon-derived key."""
    if not key:
        raise ValueError("Cursor signing key must not be empty")
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    tag = hmac.digest(key, body, hashlib.sha256)
    return f"{_b64encode(body)}.{_b64encode(tag)}"


def decode_cursor(cursor: str, key: bytes) -> dict[str, JsonValue]:
    """Reject malformed, modified and foreign-daemon cursors uniformly."""
    if not key:
        raise ValueError("Cursor signing key must not be empty")
    try:
        body_part, tag_part = cursor.split(".")
        body, tag = _b64decode(body_part), _b64decode(tag_part)
        if not hmac.compare_digest(tag, hmac.digest(key, body, hashlib.sha256)):
            raise ValueError("Invalid signature")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Expected object")
        return payload
    except (ValueError, UnicodeError, binascii.Error):
        raise ToolError(ErrorCode.INVALID_ARGUMENT, "Invalid pagination cursor") from None
