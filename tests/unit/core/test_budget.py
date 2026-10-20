import base64
import json

import pytest

from research_mcp.core.budget import (
    TRUNCATION_MARKER,
    decode_cursor,
    encode_cursor,
    fit,
)
from research_mcp.core.envelope import SourceStatus, ToolResult, Untrusted
from research_mcp.core.errors import ErrorCode, ToolError


def test_budget_list_prefix_and_cursor():
    """AT-PLAT-31: Trim trailing items within bytes without mutating the caller."""
    original = ToolResult[list[str]](
        data=["one" * 30, "two" * 30, "three" * 30], next_cursor="next"
    )
    bound = len(
        original.model_copy(update={"data": original.data[:2], "truncated": True})
        .model_dump_json()
        .encode()
    )
    result = fit(original, bound)
    assert result.data == original.data[:2]
    assert len(result.model_dump_json().encode()) <= bound
    assert result.truncated and result.next_cursor == "next"
    assert len(original.data) == 3 and not original.truncated
    assert fit(original, 10000) == original


@pytest.mark.parametrize(
    "text", ["界🙂" * 1000, '"\\\n' * 1000], ids=["unicode", "escaped"]
)
def test_budget_long_text(text):
    """AT-PLAT-31: Shorten Unicode and escaped text using actual JSON byte size."""
    original = ToolResult[Untrusted](
        data=Untrusted(source="test", content=text), next_cursor="keep"
    )
    result = fit(original, 250)
    assert len(result.model_dump_json().encode()) <= 250
    assert result.data.content.endswith(TRUNCATION_MARKER)
    assert result.data.source == "test" and result.data.untrusted
    assert result.next_cursor == "keep" and result.truncated
    assert original.data.content == text


def test_budget_nested_and_scalar_text():
    """AT-PLAT-31: Nested lists and scalar text both fit the serialized budget."""
    nested = ToolResult(data={"records": ["x" * 100] * 20}, next_cursor="next")
    assert len(fit(nested, 250).model_dump_json().encode()) <= 250
    scalar = fit(ToolResult(data="x" * 1000), 150)
    assert scalar.data.endswith(TRUNCATION_MARKER)
    assert len(scalar.model_dump_json().encode()) <= 150


def test_impossible_budget_preserves_metadata():
    """AT-PLAT-31: Fail explicitly when immutable metadata exceeds the budget."""
    result = ToolResult(
        data=[],
        source_status=[SourceStatus(source="test", state="ok")],
        next_cursor="x" * 300,
    )
    with pytest.raises(ToolError) as error:
        fit(result, 100)
    assert error.value.code == ErrorCode.TOO_LARGE
    with pytest.raises(ToolError) as error:
        fit(result, 0)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT


def test_signed_cursor_roundtrip_and_tampering():
    """AT-PLAT-34: Sign JSON and reject tampering or foreign keys."""
    key = b"fixture-signing-material"
    payload = {"arxiv": "page-two", "crossref": None, "offset": 20}
    cursor = encode_cursor(payload, key)
    assert decode_cursor(cursor, key) == payload
    body, tag = cursor.split(".")
    assert (
        json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))) == payload
    )
    changed = base64.urlsafe_b64encode(b'{"offset":999}').rstrip(b"=").decode()
    for bad in [
        "",
        "%%%.xxx",
        cursor + ".extra",
        changed + "." + tag,
        body + ".AA",
        cursor + "=",
    ]:
        with pytest.raises(ToolError) as error:
            decode_cursor(bad, key)
        assert error.value.code == ErrorCode.INVALID_ARGUMENT
        assert str(error.value) == "Invalid pagination cursor"
    with pytest.raises(ToolError) as error:
        decode_cursor(cursor, b"foreign-fixture-material")
    assert error.value.code == ErrorCode.INVALID_ARGUMENT
