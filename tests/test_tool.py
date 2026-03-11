"""Tests for get_skills_info tool — JSON parsing, hit filtering, and response construction."""

from __future__ import annotations

from sn_api_helper_mcp.tools.get_skills_info import _extract_top_hits


def _make_hit(
    content: str = "doc content",
    path: str = "docs/test.md",
    score: float = 10.0,
) -> dict:
    return {
        "_score": score,
        "_source": {"content": content, "path": path},
    }


# ─── _extract_top_hits ───


def test_extract_standard_es_response() -> None:
    """Standard Elasticsearch response with hits.hits and hits.total."""
    data = {
        "hits": {
            "total": {"value": 46, "relation": "eq"},
            "hits": [
                _make_hit("doc1", "a.md", 15.0),
                _make_hit("doc2", "b.md", 12.0),
                _make_hit("doc3", "c.md", 10.0),
                _make_hit("doc4", "d.md", 5.0),
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=3)
    assert total == 46
    assert len(hits) == 3
    assert hits[0]["_source"]["path"] == "a.md"


def test_extract_respects_max_results() -> None:
    data = {
        "hits": {
            "total": {"value": 10},
            "hits": [_make_hit(score=10.0 - i) for i in range(10)],
        }
    }
    hits, _ = _extract_top_hits(data, max_results=1)
    assert len(hits) == 1

    hits, _ = _extract_top_hits(data, max_results=5)
    assert len(hits) == 5


def test_extract_filters_low_scoring_hits() -> None:
    """Hits scoring below 50% of top score should be excluded."""
    data = {
        "hits": {
            "total": {"value": 5},
            "hits": [
                _make_hit(score=20.0),
                _make_hit(score=15.0),
                _make_hit(score=10.0),  # exactly 50% — included
                _make_hit(score=9.0),  # below 50% — excluded
                _make_hit(score=5.0),  # well below — excluded
            ],
        }
    }
    hits, total = _extract_top_hits(data, max_results=10)
    assert total == 5
    assert len(hits) == 3  # 20.0, 15.0, 10.0


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
            _make_hit("doc1", "a.md", 10.0),
            _make_hit("doc2", "b.md", 8.0),
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


def test_cache_key_consistency() -> None:
    """Verify the cache key incorporates both query and max_results."""
    from sn_api_helper_mcp.tools.get_skills_info import _cache_key

    key1 = _cache_key("auth", 3)
    key2 = _cache_key("auth", 5)
    key3 = _cache_key("AUTH", 3)

    assert key1 != key2  # different max_results
    assert key1 == key3  # case-insensitive query normalization
