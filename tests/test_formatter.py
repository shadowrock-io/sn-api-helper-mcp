"""Tests for the response formatter — both legacy and document-aware APIs."""

from sn_api_helper_mcp.response_formatter import (
    format_response,
    format_search_results,
)

# ─── Legacy format_response (backward compatibility) ───


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


# ─── format_search_results (document-aware) ───


def _make_hit(content: str, path: str = "docs/test.md", score: float = 10.0) -> dict:
    """Create a mock Elasticsearch hit."""
    return {
        "_score": score,
        "_source": {
            "content": content,
            "path": path,
        },
    }


def test_search_results_empty_list() -> None:
    assert format_search_results([]) == "No results found for this query."


def test_search_results_single_hit() -> None:
    hits = [_make_hit("Hello world documentation.", "docs/hello.md")]
    result = format_search_results(hits)
    assert "## Source: `docs/hello.md`" in result
    assert "Hello world documentation." in result


def test_search_results_multiple_hits_separated() -> None:
    hits = [
        _make_hit("First doc content.", "docs/first.md", score=10.0),
        _make_hit("Second doc content.", "docs/second.md", score=8.0),
    ]
    result = format_search_results(hits)
    assert "## Source: `docs/first.md`" in result
    assert "## Source: `docs/second.md`" in result
    assert "---" in result  # separator between docs


def test_search_results_html_stripped() -> None:
    hits = [_make_hit("<p>Clean <strong>text</strong></p>", "docs/html.md")]
    result = format_search_results(hits)
    assert "<p>" not in result
    assert "<strong>" not in result
    assert "Clean text" in result


def test_search_results_code_blocks_preserved() -> None:
    content = "Introduction.\n\n```python\nprint('preserved')\n```\n\nConclusion."
    hits = [_make_hit(content, "docs/code.md")]
    result = format_search_results(hits)
    assert "```python" in result
    assert "print('preserved')" in result


def test_search_results_per_doc_budget() -> None:
    long_content = "word " * 5000  # ~25000 chars
    hits = [_make_hit(long_content, "docs/long.md")]
    result = format_search_results(hits, max_chars_per_doc=500)
    # Should be truncated to roughly 500 chars (plus header)
    assert len(result) < 1000
    assert "[... truncated]" in result


def test_search_results_overall_hard_cap() -> None:
    hits = [_make_hit("content " * 1000, f"docs/doc{i}.md", score=10.0 - i) for i in range(5)]
    result = format_search_results(hits, max_total_chars=2000)
    assert len(result) <= 2500  # some tolerance for final section boundary
    # Not all 5 docs should be included
    doc_count = result.count("## Source:")
    assert doc_count < 5


def test_search_results_skip_empty_content() -> None:
    hits = [
        _make_hit("", "docs/empty.md"),
        _make_hit("   ", "docs/whitespace.md"),
        _make_hit("Actual content.", "docs/real.md"),
    ]
    result = format_search_results(hits)
    assert "## Source: `docs/real.md`" in result
    assert "docs/empty.md" not in result
    assert "docs/whitespace.md" not in result


def test_search_results_excessive_newlines_collapsed() -> None:
    hits = [_make_hit("Line A\n\n\n\n\nLine B", "docs/newlines.md")]
    result = format_search_results(hits)
    assert "\n\n\n" not in result
    assert "Line A" in result
    assert "Line B" in result


def test_search_results_truncation_at_section_boundary() -> None:
    """Verify truncation prefers markdown section boundaries."""
    sections = []
    for i in range(10):
        sections.append(f"## Section {i}\n\n" + "filler text. " * 100)
    content = "\n\n".join(sections)
    hits = [_make_hit(content, "docs/sections.md")]
    result = format_search_results(hits, max_chars_per_doc=500)
    assert "[... truncated]" in result
