"""Tests for the response formatter — legacy, document-aware, and query-aware APIs."""

import json

from sn_api_helper_mcp.response_formatter import (
    _extract_from_json_spec,
    _format_endpoint,
    _reorder_sections_by_relevance,
    _tokenize_query,
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


def _make_hit(
    content: str,
    path: str = "docs/test.md",
    score: float = 10.0,
) -> dict:
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
    assert "---" in result


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
    long_content = "word " * 5000
    hits = [_make_hit(long_content, "docs/long.md")]
    result = format_search_results(hits, max_chars_per_doc=500)
    assert len(result) < 1000
    assert "[... truncated]" in result


def test_search_results_overall_hard_cap() -> None:
    hits = [_make_hit("content " * 1000, f"docs/doc{i}.md", score=10.0 - i) for i in range(5)]
    result = format_search_results(hits, max_total_chars=2000)
    assert len(result) <= 2500
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


# ─── _tokenize_query ───


def test_tokenize_basic() -> None:
    keywords, methods = _tokenize_query("GET document download")
    assert methods == {"get"}
    assert "document" in keywords
    assert "download" in keywords
    assert "get" not in keywords


def test_tokenize_removes_stop_words() -> None:
    keywords, methods = _tokenize_query("POST invite for signing")
    assert "for" not in keywords
    assert "invite" in keywords
    assert "signing" in keywords
    assert methods == {"post"}


def test_tokenize_empty() -> None:
    keywords, methods = _tokenize_query("")
    assert keywords == set()
    assert methods == set()


def test_tokenize_removes_short_tokens() -> None:
    keywords, _ = _tokenize_query("a b cd document")
    assert "a" not in keywords
    assert "b" not in keywords
    assert "cd" in keywords
    assert "document" in keywords


# ─── _reorder_sections_by_relevance ───


def test_reorder_promotes_matching_section() -> None:
    text = (
        "## Authentication\n\nOAuth2 setup guide.\n\n"
        "## Download\n\nDownload signed documents as PDF.\n\n"
        "## Templates\n\nManage document templates."
    )
    result = _reorder_sections_by_relevance(text, {"download", "pdf"})
    # Download section should appear before Authentication
    download_pos = result.find("## Download")
    auth_pos = result.find("## Authentication")
    assert download_pos < auth_pos


def test_reorder_preserves_preamble() -> None:
    text = (
        "Introduction paragraph.\n\n"
        "## Section A\n\nContent A.\n\n"
        "## Section B\n\nContent B with keyword."
    )
    result = _reorder_sections_by_relevance(text, {"keyword"})
    assert result.startswith("Introduction paragraph.")


def test_reorder_no_headers_unchanged() -> None:
    text = "Just plain text without any headers."
    result = _reorder_sections_by_relevance(text, {"plain"})
    assert result == text


def test_reorder_no_keywords_unchanged() -> None:
    text = "## A\n\nContent.\n\n## B\n\nMore content."
    result = _reorder_sections_by_relevance(text, set())
    assert result == text


def test_reorder_stable_for_equal_scores() -> None:
    """Sections with equal relevance scores maintain original order."""
    text = "## First\n\nContent.\n\n## Second\n\nContent.\n\n## Third\n\nContent."
    result = _reorder_sections_by_relevance(text, {"unrelated"})
    first_pos = result.find("## First")
    second_pos = result.find("## Second")
    third_pos = result.find("## Third")
    assert first_pos < second_pos < third_pos


# ─── _extract_from_json_spec ───


def _make_openapi_spec(paths: dict) -> str:
    return json.dumps({"openapi": "3.0.0", "paths": paths})


def test_extract_json_spec_matching_endpoint() -> None:
    spec = _make_openapi_spec(
        {
            "/document/{id}": {
                "get": {
                    "summary": "Get document details",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "description": "Document ID",
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/document/{id}/download": {
                "get": {
                    "summary": "Download signed document",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "description": "Document ID",
                        }
                    ],
                    "responses": {"200": {"description": "Binary PDF content"}},
                }
            },
        }
    )
    result = _extract_from_json_spec(spec, "GET document download", 5000)
    assert result is not None
    # The download endpoint should appear first
    assert "/document/{id}/download" in result
    download_pos = result.find("/download")
    details_pos = result.find("Get document details")
    # download should be before general get
    if details_pos > 0:
        assert download_pos < details_pos


def test_extract_json_spec_method_filter() -> None:
    spec = _make_openapi_spec(
        {
            "/template/{id}/bulkinvite": {
                "post": {
                    "summary": "Send bulk invite",
                    "responses": {"200": {"description": "Invites sent"}},
                },
                "get": {
                    "summary": "Get bulk invite status",
                    "responses": {"200": {"description": "Status"}},
                },
            }
        }
    )
    result = _extract_from_json_spec(spec, "POST template bulkinvite", 5000)
    assert result is not None
    # POST should appear before GET
    post_pos = result.find("POST")
    get_pos = result.find("GET")
    if get_pos > 0:
        assert post_pos < get_pos


def test_extract_json_spec_no_matching_endpoints() -> None:
    spec = _make_openapi_spec(
        {
            "/users": {
                "get": {
                    "summary": "List users",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    )
    result = _extract_from_json_spec(spec, "document download", 5000)
    assert result is None


def test_extract_json_spec_invalid_json() -> None:
    result = _extract_from_json_spec("not json {{{", "test query", 5000)
    assert result is None


def test_extract_json_spec_no_paths() -> None:
    result = _extract_from_json_spec(json.dumps({"info": {"title": "API"}}), "test", 5000)
    assert result is None


def test_extract_json_spec_budget_respected() -> None:
    """Extraction output should respect the character budget."""
    paths = {}
    for i in range(20):
        paths[f"/document/endpoint{i}"] = {
            "get": {
                "summary": f"Document endpoint {i}",
                "description": "Long description. " * 50,
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": "The ID",
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            }
        }
    spec = _make_openapi_spec(paths)
    result = _extract_from_json_spec(spec, "GET document", 2000)
    assert result is not None
    assert len(result) <= 2500  # some tolerance for truncation boundary


# ─── _format_endpoint ───


def test_format_endpoint_basic() -> None:
    operation = {
        "summary": "Download document",
        "parameters": [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Document ID",
            }
        ],
        "responses": {
            "200": {"description": "Binary PDF"},
            "404": {"description": "Not found"},
        },
    }
    result = _format_endpoint("GET", "/document/{id}/download", operation)
    assert "### `GET /document/{id}/download`" in result
    assert "Download document" in result
    assert "`id`" in result
    assert "path" in result
    assert "required" in result
    assert "`200`" in result
    assert "`404`" in result


def test_format_endpoint_with_request_body() -> None:
    operation = {
        "summary": "Create invite",
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"to": {"type": "string"}},
                    }
                }
            }
        },
        "responses": {"201": {"description": "Created"}},
    }
    result = _format_endpoint("POST", "/invite", operation)
    assert "**Request Body:**" in result
    assert "application/json" in result


# ─── Query-aware format_search_results integration ───


def test_search_results_with_query_json_spec() -> None:
    """JSON spec hit with query should extract matching endpoint."""
    spec = _make_openapi_spec(
        {
            "/document/{id}/download": {
                "get": {
                    "summary": "Download signed document as PDF",
                    "responses": {"200": {"description": "Binary PDF"}},
                }
            },
            "/document/{id}": {
                "get": {
                    "summary": "Get document details",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        }
    )
    hits = [_make_hit(spec, "reference/document.json")]
    result = format_search_results(hits, query="GET document download")
    assert "download" in result.lower()
    assert "reference/document.json" in result


def test_search_results_with_query_markdown_reorder() -> None:
    """Markdown hit with query should reorder sections by relevance."""
    content = (
        "## Overview\n\nGeneral overview text.\n\n"
        "## Webhooks\n\nWebhook event subscription details.\n\n"
        "## Authentication\n\nOAuth2 authentication flow."
    )
    hits = [_make_hit(content, "docs/sn/guides/api.md")]
    result = format_search_results(hits, query="webhook event")
    # Webhooks section should appear before Overview
    webhook_pos = result.find("## Webhooks")
    overview_pos = result.find("## Overview")
    assert webhook_pos < overview_pos


def test_search_results_query_backward_compatible() -> None:
    """Passing no query should work the same as before."""
    hits = [_make_hit("Simple content.", "docs/test.md")]
    result_no_query = format_search_results(hits)
    result_empty_query = format_search_results(hits, query="")
    assert result_no_query == result_empty_query
    assert "Simple content." in result_no_query
