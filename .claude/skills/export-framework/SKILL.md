---
name: export-framework
description: "Re-export the private thehomie repo to the public thehomie-framework repo and push both to GitHub. Runs the sanitizer, inspects the resulting public diff for suspicious runtime/state leaks (not just PII — the sanitizer's content scan misses file-category leaks), commits with a sync message, and pushes both repos. Use when the user says 'push to GitHub', 'update the framework repo', 're-export', 'sync framework', 'ship the fix public', or after any framework-level change that should be publicly visible. Also triggers on: publish framework, sanitize and push, public repo sync."
---

# /export-framework — Re-export + Push Both Repos

Private `thehomie` is the source of truth. Public `thehomie-framework` is a sanitized mirror. This skill runs the full export + push loop with **leak-class checks the sanitizer's content scanner doesn't catch**.

## Why this exists

The sanitizer (`scripts/sanitize.py`) validates *content* (PII regexes, email patterns, secrets). It does **not** validate *file categories*. On 2026-04-13 a naive run was about to push `.omc/project-memory.json`, `agent-replay-*.jsonl` (conversation replays), session checkpoints, `bot.pid`, and hook logs — the sanitizer reported "PASSED zero leaks" because none of those files contained matching PII strings. The file-category leak was caught by human visual review of the diff.

This skill bakes that visual review into the workflow so future runs can't skip it.

## Prerequisites

- Clean working tree on private `thehomie` (commit your changes first)
- Public repo path: `C:\Users\YourUser\thehomie-framework`
- Both repos must have `origin` remote configured and push access

## Workflow

### Step 1 — Preflight

Verify the private repo has no staged-but-uncommitted work that should be part of the export:

```bash
git -C ~/thehomie status --short
```

If there are uncommitted framework changes, stop and ask the user whether to commit first. Do not sanitize work-in-progress.

### Step 2 — Run the sanitizer

```bash
cd ~/thehomie && uv run python scripts/sanitize.py
```

Capture and display:
- `Included` count
- `Denied` count
- `Scrubbed` count
- Final line (`PASSED zero leaks detected` or any failure)

**If the sanitizer fails or reports leaks: stop. Do not proceed to push.**

### Step 3 — Stage and categorize the public diff (THE CRITICAL STEP)

```bash
cd ~/thehomie-framework && git add -A
git -C ~/thehomie-framework diff --cached --name-only
```

Classify every staged file into these buckets and display the result to the user:

| Bucket | Pattern | Expected? |
|--------|---------|-----------|
| **Code** | `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.sh`, `*.bat`, `*.ps1` | Yes |
| **Docs** | `*.md`, `*.txt`, `*.rst` | Yes |
| **Tests** | paths containing `/tests/` or `test_*` | Yes |
| **Config** | `*.toml`, `*.yaml`, `*.yml`, `*.json` (non-state), `.env.example` | Usually yes |
| **🚨 SUSPICIOUS** | Any of the below — flag and halt | **NO — investigate** |

Suspicious patterns (add to denylist, don't push):

- `.pid` files (ephemeral process IDs)
- `.db`, `.sqlite*`, `.sqlite3` (databases)
- `.jsonl` files under any `logs/`, `state/`, `.omc/`, `.omx/` path
- Anything matching `agent-replay-*`, `checkpoint-*`, `flush-context-*`, `session-*`
- `project-memory.json`, `hud-state.json`, `metrics.json`, `*-state.json`
- Any `.log` file
- Any `tmp/`, `cache/`, `__pycache__/` content

**If the SUSPICIOUS bucket has any entries:** stop the workflow, display the offending paths, and tell the user the sanitizer denylist has a hole. Add the pattern to `scripts/sanitize.py` (`DENY_DIRS` or `DENY_FILES`), re-run from Step 2. Do not push.

### Step 4 — Confirm the diff with the user

Show a summary:
- N files, +X/-Y lines
- Top 10 changed paths
- Link between this export and the triggering private commit(s): `git -C ~/thehomie log --oneline -5`

Ask the user to confirm before committing and pushing. Never push without explicit approval.

### Step 5 — Commit the public repo

```bash
cd ~/thehomie-framework && git commit -m "$(cat <<'EOF'
sync: <one-line summary matching private intent>

Mirrors private thehomie changes (<sha1>, <sha2>):

<2-5 bullets describing user-facing behavior change>

Signed-off-by: YourAgent
EOF
)"
```

Reference private commit SHAs so anyone reading the public history can trace back.

### Step 6 — Push both repos

```bash
git -C ~/thehomie push origin master
git -C ~/thehomie-framework push origin master
```

Capture and display both push outputs. Confirm both succeeded.

### Step 7 — Report

Summarize to the user:
- Private: `old_sha..new_sha` on `github.com/thehomie-framework/thehomie`
- Public: `old_sha..new_sha` on `github.com/SmokeAlot420/thehomie-framework`
- Files changed on public: N
- Any denylist patches added during the run

## Failure modes and recovery

| Symptom | Cause | Fix |
|--------|-------|-----|
| Sanitizer reports leak | PII pattern matched in content | Grep the reported file, redact manually in private, re-commit, re-run |
| Suspicious bucket non-empty | Denylist hole | Add `DENY_DIRS` / `DENY_FILES` entry in `scripts/sanitize.py`, commit to private, re-run |
| Nested path slipping through DENY_DIRS | `startswith()` only matches top-level | `is_denied()` already fixed to match any path segment (commit `6daef06`) — verify the fix is still in place |
| Public repo push rejected | Divergence from origin | Pull with rebase (`git pull --rebase`), re-run sanitizer, re-stage |
| `.gitignore` diff strips ignore rules for denied dirs | Sanitizer treats them as dead links | Cosmetic, not a leak — but flag to the user since downstream consumers lose the protection |

## Rules

- **Never push** without displaying the categorized diff and getting user confirmation.
- **Never silence** a suspicious-bucket hit. If a new file type shows up that doesn't belong, the fix is a denylist update, not an override.
- **Never manually copy files** between repos. The sanitizer is the single source of truth for what ships.
- **Never flip repo visibility** to public without explicit user approval.

## Canonical commit (reference implementation)

Session 2026-04-13: this skill was born from a near-miss where agent replays and project memory were about to leak. The sanitizer fix landed as `6daef06` (private) and the workflow is captured here. If you're reading this because something broke, that commit is your baseline for "what right looks like."
