"""Hermes Scout — upstream intelligence from NousResearch/hermes-agent.

Fetches merged PRs and releases, scores them for relevance to The Homie,
creates a vault research note, and optionally pings Telegram.

Usage:
    uv run python hermes_scout.py              # Live run
    uv run python hermes_scout.py --test       # Dry run (no file writes)
    uv run python hermes_scout.py --days 14    # Two-week lookback
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from config import MEMORY_DIR, STATE_DIR, now_local

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import load_dotenv  # noqa: E402 — already loaded, just for clarity
from shared import append_to_daily_log, file_lock, load_state, save_state  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration (from .env via config.py)
# ---------------------------------------------------------------------------

import os

HERMES_SCOUT_ENABLED = os.getenv("HERMES_SCOUT_ENABLED", "true").lower() == "true"
HERMES_SCOUT_REPO = os.getenv("HERMES_SCOUT_REPO", "NousResearch/hermes-agent")
HERMES_SCOUT_STATE_FILE = STATE_DIR / "hermes-scout-state.json"
RESEARCH_DIR = MEMORY_DIR / "research"

# ---------------------------------------------------------------------------
# Relevance keywords (weighted scoring)
# ---------------------------------------------------------------------------

# High relevance (weight 2) — directly competitive features
HIGH_KEYWORDS: set[str] = {
    "memory", "recall", "cognition", "dream", "self-model",
    "reflection", "entity", "compilation", "knowledge-graph",
    "vault", "context-compression", "trajectory", "consolidation",
}

# Medium relevance (weight 1) — potentially useful
MED_KEYWORDS: set[str] = {
    "hooks", "tools", "skills", "routing", "session",
    "heartbeat", "cron", "orchestration", "agent-sdk",
    "search", "embedding", "rerank", "context", "prompt",
}

# Skip keywords (score = -10, forces skip)
SKIP_KEYWORDS: set[str] = {
    "docker", "dockerfile", "ci/cd", "website", "docs-only", "i18n",
    "translation", "logo", "readme", "typo", "changelog",
}

REPO_URL = "https://github.com/{repo}"
PR_URL = "https://github.com/{repo}/pull/{number}"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def score_relevance(title: str, labels: list[str] | None = None) -> int:
    """Score a PR title + labels for relevance to The Homie. Returns 0-10."""
    text = title.lower()
    if labels:
        text += " " + " ".join(l.lower() for l in labels)

    # Check skip first
    for kw in SKIP_KEYWORDS:
        if kw in text:
            return 0

    score = 0
    for kw in HIGH_KEYWORDS:
        if kw in text:
            score += 2
    for kw in MED_KEYWORDS:
        if kw in text:
            score += 1

    return min(score, 10)


def _matched_keywords(title: str, labels: list[str] | None = None) -> list[str]:
    """Return which keywords matched for the 'Why' column."""
    text = title.lower()
    if labels:
        text += " " + " ".join(l.lower() for l in labels)
    matches = []
    for kw in HIGH_KEYWORDS:
        if kw in text:
            matches.append(kw)
    for kw in MED_KEYWORDS:
        if kw in text:
            matches.append(kw)
    return matches


def categorize(scored_prs: list[dict]) -> dict[str, list[dict]]:
    """Group PRs into port_candidates, watch_list, skipped."""
    result: dict[str, list[dict]] = {
        "port_candidates": [],
        "watch_list": [],
        "skipped": [],
    }
    for pr in scored_prs:
        s = pr["score"]
        if s >= 3:
            result["port_candidates"].append(pr)
        elif s >= 1:
            result["watch_list"].append(pr)
        else:
            result["skipped"].append(pr)

    # Sort port candidates by score descending
    result["port_candidates"].sort(key=lambda p: p["score"], reverse=True)
    return result


def generate_vault_note(
    categorized: dict[str, list[dict]],
    releases: list[dict],
    run_date: str,
    repo: str,
    total_scanned: int,
) -> str:
    """Render a markdown vault note with frontmatter."""
    port = categorized["port_candidates"]
    watch = categorized["watch_list"]
    skipped_count = len(categorized["skipped"])

    # Build summary line
    if port:
        top_titles = ", ".join(p["title"][:40] for p in port[:3])
        summary = f"Week of {run_date}: {len(port)} port candidates — {top_titles}"
    else:
        summary = f"Week of {run_date}: no port candidates from {total_scanned} PRs"

    lines = [
        "---",
        "tags: [research, hermes-agent, upstream-scout]",
        "status: current",
        f"date: {run_date}",
        f'source: "github:{repo}"',
        "scout_run: true",
        f"prs_scanned: {total_scanned}",
        f"port_candidates: {len(port)}",
        f'summary: "{summary}"',
        "related:",
        '  - "[[MOC-thehomie]]"',
        "---",
        "",
        f"# Hermes Scout — Week of {run_date}",
        "",
    ]

    # Port Candidates
    if port:
        lines.append("## Port Candidates (score >= 3)")
        lines.append("")
        lines.append("| PR | Title | Score | Why |")
        lines.append("|----|-------|-------|-----|")
        for p in port:
            pr_link = f"[#{p['number']}]({PR_URL.format(repo=repo, number=p['number'])})"
            why = ", ".join(p.get("keywords", [])[:4])
            lines.append(f"| {pr_link} | {p['title']} | {p['score']} | {why} |")
        lines.append("")
    else:
        lines.append("## Port Candidates")
        lines.append("")
        lines.append("None this week.")
        lines.append("")

    # Watch List
    if watch:
        lines.append("## Watch List (score 1-2)")
        lines.append("")
        for p in watch:
            pr_link = f"[#{p['number']}]({PR_URL.format(repo=repo, number=p['number'])})"
            lines.append(f"- {pr_link} — {p['title']} ({p['score']})")
        lines.append("")

    # Releases
    if releases:
        lines.append("## Releases")
        lines.append("")
        for r in releases:
            lines.append(f"- **{r.get('tag_name', 'unknown')}** — {r.get('name', 'No title')}")
        lines.append("")

    # Skipped
    lines.append(f"## Skipped: {skipped_count} PRs (provider-specific, UI, docs)")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub API (via gh CLI)
# ---------------------------------------------------------------------------


def _gh_api(endpoint: str) -> list[dict] | dict:
    """Call gh api and return parsed JSON."""
    cmd = ["gh", "api", endpoint]
    result = subprocess.run(
        cmd, capture_output=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        print(f"[hermes_scout] gh api error: {result.stderr[:200]}")
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # --paginate can produce multiple JSON arrays; merge them
        merged = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, list):
                    merged.extend(parsed)
                else:
                    merged.append(parsed)
            except json.JSONDecodeError:
                continue
        return merged


def fetch_merged_prs(repo: str, days: int) -> list[dict]:
    """Fetch recently merged PRs from the repo."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    endpoint = (
        f"repos/{repo}/pulls?state=closed&sort=updated"
        f"&direction=desc&per_page=100"
    )
    prs = _gh_api(endpoint)
    if not isinstance(prs, list):
        return []

    merged = []
    for pr in prs:
        merged_at = pr.get("merged_at")
        if not merged_at:
            continue
        if merged_at >= since[:10]:  # Compare date strings
            merged.append({
                "number": pr["number"],
                "title": pr["title"],
                "user": pr.get("user", {}).get("login", "unknown"),
                "merged_at": merged_at[:10],
                "labels": [l["name"] for l in pr.get("labels", [])],
            })

    return merged


def fetch_releases(repo: str, days: int) -> list[dict]:
    """Fetch recent releases."""
    releases = _gh_api(f"repos/{repo}/releases?per_page=5")
    if not isinstance(releases, list):
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
    recent = []
    for r in releases:
        published = (r.get("published_at") or "")[:10]
        if published >= since:
            recent.append({
                "tag_name": r.get("tag_name", ""),
                "name": r.get("name", ""),
                "published_at": published,
            })
    return recent


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------


def _send_telegram(text: str) -> bool:
    """Send a message via Telegram bot. Returns True on success."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    user_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    if not token or not user_ids:
        return False

    import urllib.request
    import urllib.parse

    chat_id = user_ids.split(",")[0].strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:
        print(f"[hermes_scout] Telegram send failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_hermes_scout(
    test_mode: bool = False,
    days: int = 7,
) -> str | None:
    """Run the Hermes Scout pipeline. Returns summary or 'HERMES_SILENT'."""
    if not HERMES_SCOUT_ENABLED:
        print(f"[{now_local()}] Hermes Scout disabled (HERMES_SCOUT_ENABLED=false)")
        return None

    repo = HERMES_SCOUT_REPO
    run_date = date.today().isoformat()
    print(f"[{now_local()}] Hermes Scout: scanning {repo} (last {days} days)")

    # Fetch data
    prs = fetch_merged_prs(repo, days)
    releases = fetch_releases(repo, days)

    if not prs and not releases:
        print(f"[{now_local()}] Hermes Scout: no activity in last {days} days")
        if not test_mode:
            save_state({
                "last_run": now_local(),
                "prs_scanned": 0,
                "port_candidates": 0,
                "result": "silent",
            }, HERMES_SCOUT_STATE_FILE)
        return "HERMES_SILENT"

    # Score and categorize
    scored = []
    for pr in prs:
        s = score_relevance(pr["title"], pr.get("labels"))
        pr["score"] = s
        pr["keywords"] = _matched_keywords(pr["title"], pr.get("labels"))
        scored.append(pr)

    categorized = categorize(scored)
    port_count = len(categorized["port_candidates"])

    # Generate vault note
    note_content = generate_vault_note(
        categorized, releases, run_date, repo, len(prs),
    )

    if test_mode:
        print(f"\n--- DRY RUN ---\n{note_content[:1000]}\n--- END ---")
        print(f"\nPort candidates: {port_count}, Watch: {len(categorized['watch_list'])}, Skipped: {len(categorized['skipped'])}")
        return note_content

    # Write vault note
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    note_path = RESEARCH_DIR / f"hermes-scout-{run_date}.md"
    note_path.write_text(note_content, encoding="utf-8")
    print(f"[{now_local()}] Vault note: {note_path.relative_to(MEMORY_DIR)}")

    # Send Telegram summary
    if port_count > 0:
        top3 = categorized["port_candidates"][:3]
        tg_lines = [f"<b>Hermes Scout</b> — {port_count} port candidate(s)"]
        for p in top3:
            tg_lines.append(f"  #{p['number']}: {p['title']} (score {p['score']})")
        tg_lines.append(f"\nFull digest: research/hermes-scout-{run_date}.md")
        _send_telegram("\n".join(tg_lines))

    # Update state
    save_state({
        "last_run": now_local(),
        "last_pr_checked": max((p["number"] for p in prs), default=0),
        "prs_scanned": len(prs),
        "port_candidates": port_count,
        "vault_note": f"research/hermes-scout-{run_date}.md",
        "result": "scouted",
    }, HERMES_SCOUT_STATE_FILE)

    # Append to daily log
    append_to_daily_log(
        f"Hermes Scout: {len(prs)} PRs scanned, {port_count} port candidates from {repo}",
        "Hermes Scout",
    )

    summary = f"Scouted {len(prs)} PRs, {port_count} port candidates, {len(releases)} releases"
    print(f"[{now_local()}] {summary}")
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes Scout — upstream intelligence")
    parser.add_argument("--test", action="store_true", help="Dry run (no file writes)")
    parser.add_argument("--days", type=int, default=7, help="Days to look back")
    args = parser.parse_args()

    result = asyncio.run(run_hermes_scout(test_mode=args.test, days=args.days))
    if result and result != "HERMES_SILENT":
        print(f"\nResult: {result[:300]}")


if __name__ == "__main__":
    main()
