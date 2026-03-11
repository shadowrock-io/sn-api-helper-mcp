"""Tests for the response formatter."""

from sn_api_helper_mcp.response_formatter import format_response


def test_empty_input() -> None:
    assert format_response("") == "No information available for this query."
    assert format_response("   ") == "No information available for this query."


def test_html_stripping() -> None:
    result = format_response("<div>Hello <b>World</b></div>")
    assert "<div>" not in result
    assert "<b>" not in result
    assert "Hello" in result
    assert "World" in result


def test_code_block_preservation() -> None:
    raw = "Some prose\n\n```python\nprint('hello')\n```\n\nMore prose"
    result = format_response(raw)
    assert "```python" in result
    assert "print('hello')" in result


def test_excessive_newlines_collapsed() -> None:
    raw = "Line 1\n\n\n\n\nLine 2"
    result = format_response(raw)
    assert "\n\n\n" not in result
    assert "Line 1" in result
    assert "Line 2" in result


def test_truncation_with_budget() -> None:
    long_prose = "word " * 2000
    result = format_response(long_prose, max_chars=100)
    assert len(result) < len(long_prose)
    assert "..." in result


def test_headers_preserved_during_truncation() -> None:
    lines = ["# Header 1", ""] + ["filler " * 50] * 20 + ["", "# Header 2", "More text"]
    raw = "\n".join(lines)
    result = format_response(raw, max_chars=200)
    assert "# Header 1" in result


def test_code_not_trimmed_by_prose_budget() -> None:
    code = "```python\n" + "x = 1\n" * 50 + "```"
    raw = f"Short intro.\n\n{code}\n\nShort outro."
    result = format_response(raw, max_chars=500)
    assert "x = 1" in result
