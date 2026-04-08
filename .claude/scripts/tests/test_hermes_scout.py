"""Tests for hermes_scout.py — upstream intelligence pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure scripts dir on path
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from hermes_scout import (
    categorize,
    generate_vault_note,
    score_relevance,
    _matched_keywords,
)


# ---------------------------------------------------------------------------
# score_relevance
# ---------------------------------------------------------------------------

class TestScoreRelevance:
    def test_high_keywords_score_high(self):
        assert score_relevance("feat(memory): recall pipeline") >= 3

    def test_multiple_high_keywords(self):
        assert score_relevance("feat: dream consolidation with recall") >= 4

    def test_skip_keywords_zero(self):
        assert score_relevance("fix: Docker build") == 0
        assert score_relevance("docs: update README") == 0
        assert score_relevance("chore: fix typo in changelog") == 0

    def test_medium_keywords(self):
        s = score_relevance("feat(hooks): new lifecycle event")
        assert 1 <= s <= 2

    def test_no_match_zero(self):
        assert score_relevance("fix(minimax): correct model catalog") == 0

    def test_labels_included(self):
        s = score_relevance("fix: something", ["memory", "recall"])
        assert s >= 3

    def test_max_score_capped(self):
        title = "memory recall cognition dream self-model reflection entity compilation vault"
        assert score_relevance(title) <= 10


# ---------------------------------------------------------------------------
# _matched_keywords
# ---------------------------------------------------------------------------

class TestMatchedKeywords:
    def test_returns_matches(self):
        kws = _matched_keywords("feat(memory): recall pipeline")
        assert "memory" in kws
        assert "recall" in kws

    def test_empty_on_no_match(self):
        assert _matched_keywords("fix: provider URL") == []


# ---------------------------------------------------------------------------
# categorize
# ---------------------------------------------------------------------------

class TestCategorize:
    def test_groups_correctly(self):
        prs = [
            {"number": 1, "title": "a", "score": 5},
            {"number": 2, "title": "b", "score": 2},
            {"number": 3, "title": "c", "score": 0},
        ]
        result = categorize(prs)
        assert len(result["port_candidates"]) == 1
        assert len(result["watch_list"]) == 1
        assert len(result["skipped"]) == 1
        assert result["port_candidates"][0]["number"] == 1

    def test_sort_by_score_desc(self):
        prs = [
            {"number": 1, "title": "a", "score": 3},
            {"number": 2, "title": "b", "score": 5},
        ]
        result = categorize(prs)
        assert result["port_candidates"][0]["number"] == 2

    def test_empty_input(self):
        result = categorize([])
        assert result["port_candidates"] == []
        assert result["watch_list"] == []
        assert result["skipped"] == []


# ---------------------------------------------------------------------------
# generate_vault_note
# ---------------------------------------------------------------------------

class TestGenerateVaultNote:
    def _sample_categorized(self):
        return {
            "port_candidates": [
                {"number": 42, "title": "feat: memory recall", "score": 4, "keywords": ["memory", "recall"]},
            ],
            "watch_list": [
                {"number": 99, "title": "feat(hooks): lifecycle", "score": 1, "keywords": ["hooks"]},
            ],
            "skipped": [{"number": 100, "title": "fix: Docker", "score": 0}],
        }

    def test_has_frontmatter(self):
        note = generate_vault_note(self._sample_categorized(), [], "2026-04-13", "NousResearch/hermes-agent", 50)
        assert note.startswith("---")
        assert "tags: [research, hermes-agent, upstream-scout]" in note
        assert "date: 2026-04-13" in note
        assert "scout_run: true" in note

    def test_has_port_candidates_table(self):
        note = generate_vault_note(self._sample_categorized(), [], "2026-04-13", "NousResearch/hermes-agent", 50)
        assert "## Port Candidates" in note
        assert "#42" in note
        assert "feat: memory recall" in note

    def test_has_watch_list(self):
        note = generate_vault_note(self._sample_categorized(), [], "2026-04-13", "NousResearch/hermes-agent", 50)
        assert "## Watch List" in note
        assert "#99" in note

    def test_has_skipped_count(self):
        note = generate_vault_note(self._sample_categorized(), [], "2026-04-13", "NousResearch/hermes-agent", 50)
        assert "Skipped: 1 PRs" in note

    def test_releases_section(self):
        releases = [{"tag_name": "v0.7.1", "name": "Bug fixes", "published_at": "2026-04-10"}]
        note = generate_vault_note(self._sample_categorized(), releases, "2026-04-13", "NousResearch/hermes-agent", 50)
        assert "## Releases" in note
        assert "v0.7.1" in note

    def test_no_port_candidates(self):
        cat = {"port_candidates": [], "watch_list": [], "skipped": []}
        note = generate_vault_note(cat, [], "2026-04-13", "NousResearch/hermes-agent", 0)
        assert "None this week" in note

    def test_summary_in_frontmatter(self):
        note = generate_vault_note(self._sample_categorized(), [], "2026-04-13", "NousResearch/hermes-agent", 50)
        assert "prs_scanned: 50" in note
        assert "port_candidates: 1" in note
