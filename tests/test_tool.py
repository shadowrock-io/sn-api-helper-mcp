"""Tests for get_skills_info tool.

Covers JSON parsing, hit filtering, re-ranking, and response construction.
"""

from __future__ import annotations

from sn_api_helper_mcp.tools.get_skills_info import (
    CONTENT_TYPE_API_SPEC,
    CONTENT_TYPE_GUIDE,
    CONTENT_TYPE_INTEGRATION,
    CONTENT_TYPE_OTHER,
    _cache_key,
    _classify_content_type,
    _content_boost,
    _extract_top_hits,
)


def _make_hit(
    content: str = "doc content",
    path: str = "docs/test.md",
    score: float = 10.0,
) -> dict:
    return {
        "_score": score,
        "_source": {"content": content, "path": path},
    }


# ─── _classify_content_type ───


def test_classify_api_spec() -> None:
    assert _classify_content_type("reference/oauth2.json") == CONTENT_TYPE_API_SPEC
    assert _classify_content_type("reference/document/invite.json") == CONTENT_TYPE_API_SPEC


def test_classify_guide() -> None:
    assert _classify_content_type("docs/sn/guides/embedded-signing.md") == CONTENT_TYPE_GUIDE
    path = "docs/sn/guides/ai_tools/signnow-mcp-server.md"
    assert _classify_content_type(path) == CONTENT_TYPE_GUIDE


def test_classify_integration() -> None:
    sf = "docs/integration/salesforce/setup.md"
    assert _classify_content_type(sf) == CONTENT_TYPE_INTEGRATION
    ns = "docs/integration/netsuite/config.md"
    assert _classify_content_type(ns) == CONTENT_TYPE_INTEGRATION


def test_classify_other() -> None:
    assert _classify_content_type("docs/sn/changelog.md") == CONTENT_TYPE_OTHER
    assert _classify_content_type("some/unknown/path.md") == CONTENT_TYPE_OTHER


# ─── _content_boost ───


def test_boost_api_spec_promoted() -> None:
    """API specs get 1.5x boost."""
    boost = _content_boost("reference/oauth2.json")
    assert boost == 1.5


def test_boost_guide_neutral() -> None:
    """Guides get 1.0x (neutral) boost."""
    boost = _content_boost("docs/sn/guides/embedded-signing.md")
    assert boost == 1.0


def test_boost_integration_demoted() -> None:
    """Integration guides get 0.3x (demoted) boost."""
    boost = _content_boost("docs/integration/salesforce/setup.md")
    assert boost == 0.3


def test_boost_noise_heavily_penalised() -> None:
    """Changelog and MCP meta-doc get 0.1x (heavy penalty)."""
    assert _content_boost("docs/sn/changelog.md") == 0.1
    assert _content_boost("docs/sn/guides/ai_tools/signnow-mcp-server.md") == 0.1


def test_boost_unknown_path_default() -> None:
    """Unknown paths get 0.7x (other) boost."""
    boost = _content_boost("some/random/doc.md")
    assert boost == 0.7


# ─── _extract_top_hits — basic extraction ───


def test_extract_standard_es_response() -> None:
    """Standard Elasticsearch response with hits.hits and hits.total."""
    data = {
        "hits": {
            "total": {"value": 46, "relation": "eq"},
            "hits": [
                _make_hit("doc1", "reference/a.json", 15.0),
                _make_hit("doc2", "reference/b.json", 12.0),
                _make_hit("doc3", "reference/c.json", 10.0),
                _make_hit("doc4", "reference/d.json", 5.0),
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=3)
    assert total == 46
    assert len(hits) == 3


def test_extract_respects_max_results() -> None:
    data = {
        "hits": {
            "total": {"value": 10},
            "hits": [_make_hit(path=f"reference/doc{i}.json", score=10.0 - i) for i in range(10)],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=1)
    assert len(hits) == 1

    hits, _ = _extract_top_hits(data, max_results=5)
    assert len(hits) == 5


def test_extract_filters_low_scoring_hits() -> None:
    """Hits scoring below 50% of top adjusted score should be excluded."""
    data = {
        "hits": {
            "total": {"value": 5},
            "hits": [
                _make_hit(path="reference/a.json", score=20.0),  # adjusted: 30.0
                _make_hit(path="reference/b.json", score=15.0),  # adjusted: 22.5
                _make_hit(path="reference/c.json", score=10.0),  # adjusted: 15.0 = 50% of 30
                _make_hit(path="reference/d.json", score=9.0),  # adjusted: 13.5 < 15 — excluded
                _make_hit(path="reference/e.json", score=5.0),  # adjusted: 7.5 — excluded
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=10)
    assert total == 5
    assert len(hits) == 3


def test_extract_empty_hits() -> None:
    data = {"hits": {"total": {"value": 0}, "hits": []}}
    hits, total = _extract_top_hits(data, max_results=3)
    assert hits == []
    assert total == 0


def test_extract_no_hits_key() -> None:
    """Handles malformed response with no hits key."""
    data = {"error": "something went wrong"}
    hits, total = _extract_top_hits(data, max_results=3)
    assert hits == []
    assert total == 0


def test_extract_total_as_integer() -> None:
    """Some ES versions return total as a plain integer."""
    data = {
        "hits": {
            "total": 42,
            "hits": [_make_hit(score=10.0)],
        }
    }
    hits, total = _extract_top_hits(data, max_results=3)
    assert total == 42
    assert len(hits) == 1


def test_extract_flat_hits_list() -> None:
    """Handle case where response is just a list of hits (no wrapper)."""
    data = {
        "hits": [
            _make_hit("doc1", "reference/a.json", 10.0),
            _make_hit("doc2", "reference/b.json", 8.0),
        ]
    }
    hits, total = _extract_top_hits(data, max_results=3)
    assert len(hits) == 2
    assert total == 2


def test_extract_score_threshold_with_equal_scores() -> None:
    """All equal scores should pass the threshold."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                _make_hit(score=10.0),
                _make_hit(score=10.0),
                _make_hit(score=10.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=5)
    assert len(hits) == 3


# ─── _extract_top_hits — re-ranking ───


def test_reranking_api_spec_beats_integration() -> None:
    """API spec at lower ES score should outrank integration guide at higher ES score after boost.

    Integration (10.0 * 0.3 = 3.0) falls below 50% threshold of API spec (8.0 * 1.5 = 12.0),
    so integration is excluded entirely.
    """
    data = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                # Integration at ES score 10.0 → adjusted 10.0 * 0.3 = 3.0
                _make_hit("integration doc", "docs/integration/salesforce/auth.md", 10.0),
                # API spec at ES score 8.0 → adjusted 8.0 * 1.5 = 12.0
                _make_hit("api spec doc", "reference/oauth2.json", 8.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=2)
    # API spec should be first; integration excluded by threshold (3.0 < 6.0)
    assert len(hits) == 1
    assert hits[0]["_source"]["path"] == "reference/oauth2.json"


def test_reranking_api_spec_above_integration_when_both_qualify() -> None:
    """When both pass threshold, API spec still ranks above integration."""
    data = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                # Integration at high ES score → adjusted 40.0 * 0.3 = 12.0
                _make_hit("integration doc", "docs/integration/salesforce/auth.md", 40.0),
                # API spec → adjusted 10.0 * 1.5 = 15.0
                _make_hit("api spec doc", "reference/oauth2.json", 10.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=2)
    # Both pass threshold (12.0 >= 7.5), API spec ranks first
    assert len(hits) == 2
    assert hits[0]["_source"]["path"] == "reference/oauth2.json"
    assert hits[1]["_source"]["path"] == "docs/integration/salesforce/auth.md"


def test_reranking_guide_vs_integration() -> None:
    """Guide at same ES score as integration guide should rank higher."""
    data = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                _make_hit("integration", "docs/integration/netsuite/setup.md", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded-signing.md", 10.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=2)
    # Guide (1.0x = 10.0) should beat integration (0.3x = 3.0)
    assert hits[0]["_source"]["path"] == "docs/sn/guides/embedded-signing.md"


def test_reranking_noise_suppressed() -> None:
    """Noise documents (changelog, MCP meta-doc) are heavily penalised."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                # Changelog at high ES score → adjusted 15.0 * 0.1 = 1.5
                _make_hit("changelog", "docs/sn/changelog.md", 15.0),
                # MCP meta-doc at high ES score → adjusted 12.0 * 0.1 = 1.2
                _make_hit("mcp doc", "docs/sn/guides/ai_tools/signnow-mcp-server.md", 12.0),
                # Normal doc at lower ES score → adjusted 5.0 * 0.7 = 3.5
                _make_hit("normal", "docs/sn/overview.md", 5.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=3)
    # Normal doc should be first, noise demoted
    assert hits[0]["_source"]["path"] == "docs/sn/overview.md"


def test_reranking_noise_excluded_by_threshold() -> None:
    """Noise documents may fall below the 50% threshold and be excluded entirely."""
    data = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                # API spec → adjusted 10.0 * 1.5 = 15.0
                _make_hit("api spec", "reference/invite.json", 10.0),
                # Changelog → adjusted 10.0 * 0.1 = 1.0 (< 7.5 threshold)
                _make_hit("changelog", "docs/sn/changelog.md", 10.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=5)
    assert len(hits) == 1
    assert hits[0]["_source"]["path"] == "reference/invite.json"


# ─── _extract_top_hits — content_type filtering ───


def test_content_type_filter_api_spec() -> None:
    """content_type='api-spec' should return only API spec hits."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                _make_hit("api", "reference/oauth2.json", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded.md", 12.0),
                _make_hit("integration", "docs/integration/sf/setup.md", 8.0),
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=5, content_type="api-spec")
    assert total == 3  # total_available is pre-filter count
    assert len(hits) == 1
    assert hits[0]["_source"]["path"] == "reference/oauth2.json"


def test_content_type_filter_guide() -> None:
    """content_type='guide' should return only guide hits."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                _make_hit("api", "reference/oauth2.json", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded.md", 12.0),
                _make_hit("integration", "docs/integration/sf/setup.md", 8.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=5, content_type="guide")
    assert len(hits) == 1
    assert hits[0]["_source"]["path"] == "docs/sn/guides/embedded.md"


def test_content_type_filter_integration() -> None:
    """content_type='integration' should return only integration hits."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                _make_hit("api", "reference/oauth2.json", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded.md", 12.0),
                _make_hit("integration", "docs/integration/sf/setup.md", 8.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=5, content_type="integration")
    assert len(hits) == 1
    assert hits[0]["_source"]["path"] == "docs/integration/sf/setup.md"


def test_content_type_filter_no_matches() -> None:
    """content_type filter with no matching docs returns empty list."""
    data = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                _make_hit("api", "reference/oauth2.json", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded.md", 12.0),
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=5, content_type="integration")
    assert len(hits) == 0
    assert total == 2


def test_content_type_all_returns_mixed() -> None:
    """content_type='all' returns hits from all types, re-ranked."""
    data = {
        "hits": {
            "total": {"value": 3},
            "hits": [
                _make_hit("integration", "docs/integration/sf/setup.md", 10.0),
                _make_hit("api", "reference/oauth2.json", 10.0),
                _make_hit("guide", "docs/sn/guides/embedded.md", 10.0),
            ],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=5, content_type="all")
    # All same ES score → after boost: api=15, guide=10, integration=3
    assert hits[0]["_source"]["path"] == "reference/oauth2.json"
    assert hits[1]["_source"]["path"] == "docs/sn/guides/embedded.md"
    # Integration may be excluded by threshold (3.0 < 7.5)


# ─── _cache_key ───


def test_cache_key_consistency() -> None:
    """Verify the cache key incorporates query, max_results, and content_type."""
    key1 = _cache_key("auth", 3)
    key2 = _cache_key("auth", 5)
    key3 = _cache_key("AUTH", 3)

    assert key1 != key2  # different max_results
    assert key1 == key3  # case-insensitive query normalization


def test_cache_key_includes_content_type() -> None:
    """Cache key varies by content_type."""
    key_all = _cache_key("auth", 3, "all")
    key_spec = _cache_key("auth", 3, "api-spec")
    key_guide = _cache_key("auth", 3, "guide")

    assert key_all != key_spec
    assert key_spec != key_guide
    assert key_all != key_guide


def test_cache_key_default_content_type() -> None:
    """Default content_type is 'all'."""
    key_default = _cache_key("auth", 3)
    key_explicit = _cache_key("auth", 3, "all")

    assert key_default == key_explicit
