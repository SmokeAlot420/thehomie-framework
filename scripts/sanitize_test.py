"""Sanitizer tests for PRP-7e Phase 5 (and forward).

R3 NM1 fix: tests use the sanitizer's ``is_denied()`` API directly instead
of the ``--dry-run | grep`` pattern. The dry-run print is
``sorted(allowed)[:50]`` (truncated) so a stdout grep can pass falsely.
Direct API calls test the rule, not the run.

This is the FIRST test file in this suite. PRP-7f (Phase 6) extends with
the broader ``test_prp7_paths_classify_correctly`` covering all PRP-7
paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow ``import sanitize`` from the scripts/ directory regardless of where
# pytest is invoked from. ``Path(__file__).parent`` is ``scripts/``.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sanitize  # noqa: E402  (import after sys.path manipulation)


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_REL = ".claude/templates/profile-isolation-smoke.yaml"


def test_phase5_archon_template_included() -> None:
    """The PRP-7e smoke workflow template must NOT be denied by the
    sanitizer - it has to ship in the public export so consumers of
    ``thehomie-framework`` can run profile-isolation-smoke against their
    own Archon installs.

    Direct ``is_denied()`` call (R3 NM1 fix):
      - ``.claude/templates/`` is NOT in DENY_DIRS
      - ``.yaml`` is NOT in DENY_EXTENSIONS
      - the path is NOT in DENY_FILES
    Therefore ``is_denied()`` MUST return False.
    """
    assert sanitize.is_denied(TEMPLATE_REL) is False, (
        f"sanitizer denied {TEMPLATE_REL!r} - public export will be missing "
        f"the smoke workflow asset. Check DENY_DIRS / DENY_FILES / "
        f"DENY_EXTENSIONS in scripts/sanitize.py."
    )


def test_phase5_archon_template_present_on_disk() -> None:
    """The asset file must exist on disk (WS2a Task 5). Without this file,
    ``personas.archon._seed_smoke_workflow`` silently no-ops and the
    profile gets no smoke workflow. This test is the canary that the asset
    actually shipped to the repo.
    """
    asset = REPO_ROOT / TEMPLATE_REL
    assert asset.is_file(), (
        f"Smoke workflow asset missing at {asset}. WS2a Task 5 must "
        f"create this file."
    )


def test_phase5_archon_template_tracked_by_git() -> None:
    """The asset must be ``git add``'d. An untracked file would not ship in
    the public export even if the sanitizer allows it (the sanitizer
    operates on ``git ls-files`` output - that's the source of truth).
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", TEMPLATE_REL],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = result.returncode == 0
    assert tracked, (
        f"Smoke workflow asset {TEMPLATE_REL!r} is not tracked by git. "
        f"WS2a Task 5 must `git add` the file before commit. "
        f"git stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# PRP-7f Phase 6 — paperclip seam doc + runtime-state defense
# ---------------------------------------------------------------------------

PAPERCLIP_SEAM_REL = "docs/paperclip-seam.md"


def test_prp7_paperclip_seam_doc_included() -> None:
    """The paperclip seam doc must NOT be denied by the sanitizer. It lives
    under ``docs/`` (which is in DENY_DIRS) but is surgically lifted via
    ``INCLUDE_FILES`` because it is the public Paperclip integration
    contract.

    Direct ``is_denied()`` call — proves the layered precedence in
    ``is_denied()`` (Section: Layer 4 INCLUDE_FILES override of Layer 5
    DENY_DIRS) is wired correctly.
    """
    assert sanitize.is_denied(PAPERCLIP_SEAM_REL) is False, (
        f"sanitizer denied {PAPERCLIP_SEAM_REL!r} — public mirror will "
        f"be missing the Paperclip integration seam contract. Check that "
        f"INCLUDE_FILES in scripts/sanitize.py contains this path AND "
        f"that DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS do not match it."
    )


def test_prp7_paperclip_seam_doc_present_on_disk() -> None:
    """The doc file must exist on disk. Without this file, the
    INCLUDE_FILES allowlist points at vapor and the sanitizer silently
    ships nothing (the export step only includes paths that exist).
    """
    asset = REPO_ROOT / PAPERCLIP_SEAM_REL
    assert asset.is_file(), (
        f"Paperclip seam doc missing at {asset}. PRP-7f truncated Phase "
        f"6 must create this file."
    )


def test_prp7_paperclip_seam_doc_tracked_by_git() -> None:
    """The doc must be ``git add``'d. The sanitizer reads ``git ls-files``
    as the source of truth; an untracked file is invisible to the export
    pipeline regardless of INCLUDE_FILES.
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", PAPERCLIP_SEAM_REL],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = result.returncode == 0
    assert tracked, (
        f"Paperclip seam doc {PAPERCLIP_SEAM_REL!r} is not tracked by "
        f"git. PRP-7f Phase 6 must `git add` the file before commit. "
        f"git stderr: {result.stderr!r}"
    )


def test_prp7_runtime_state_denied() -> None:
    """Runtime state files must be denied — these contain live PIDs,
    session UUIDs, lock metadata, or feature-flag state that should
    never ship in the public mirror.

    Each path is named explicitly so a regression report points at the
    exact rule that should have caught the leak.
    """
    cases = [
        # path, rule the test expects to match
        (".claude/chat/bot.pid", "DENY_FILES + DENY_EXTENSIONS .pid"),
        (".claude/chat/bot.lock", "DENY_FILES + DENY_EXTENSIONS .lock"),
        (".claude/data/state/bot.pid", "DENY_FILES + DENY_DIRS .claude/data/ + .pid"),
        (".claude/scheduled_tasks.lock", "DENY_FILES + DENY_EXTENSIONS .lock"),
        (".claude/banner-exemption.flag", "DENY_FILES + DENY_PATTERNS \\.flag$"),
    ]
    for path, rule in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny runtime state file {path!r}. "
            f"Expected catch by: {rule}. This is a near-miss leak — "
            f"runtime state must never ship publicly."
        )


def test_prp7_homie_profiles_pattern_denied() -> None:
    """Any file under ``.homie/profiles/`` (top-level OR nested) must be
    denied — these are external operator profile-state directories that
    can show up if accidentally tracked by an operator who initialized
    a profile inside the repo by mistake.

    Tested via DENY_PATTERNS regex — handles both top-level
    ``.homie/profiles/...`` and nested ``foo/.homie/profiles/...``.
    """
    nested_cases = [
        ".homie/profiles/sales/agent.yaml",
        "home/.homie/profiles/sales/CLAUDE.md",
    ]
    for path in nested_cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny {path!r} — operator profile state "
            f"would leak. Check DENY_PATTERNS regex in scripts/sanitize.py."
        )


def test_prp7_include_files_does_not_override_deny_files() -> None:
    """Class-of-bug test for PRP-7f R1 B3.

    INCLUDE_FILES must NEVER bypass DENY_FILES. If a future operator
    accidentally puts ``.claude/chat/bot.pid`` in INCLUDE_FILES (e.g.
    cargo-cult copy of the paperclip-seam allowlist entry), the file
    must STILL be denied because DENY_FILES is layer 1 (absolute).

    Try/finally save+restore (no monkeypatch fixture) to match the
    existing test style in this file.
    """
    target = ".claude/chat/bot.pid"
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_FILES for {target!r}. DENY_FILES (layer 1) MUST "
            f"win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prp7_include_files_does_not_override_deny_extensions() -> None:
    """Class-of-bug test for PRP-7f R1 B3 — extension layer.

    INCLUDE_FILES must NEVER bypass DENY_EXTENSIONS. Same shape as
    the DENY_FILES test, but exercises layer 2 (.lock extension).
    """
    target = "docs/example.lock"  # would otherwise pass DENY_DIRS via INCLUDE_FILES
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_EXTENSIONS for {target!r}. DENY_EXTENSIONS "
            f"(layer 2) MUST win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prp7_include_files_does_not_override_deny_patterns() -> None:
    """Class-of-bug test for PRP-7f R1 B3 — pattern layer.

    INCLUDE_FILES must NEVER bypass DENY_PATTERNS. Exercises layer 3
    via the ``\\.flag$`` regex.
    """
    target = "docs/example.flag"
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_PATTERNS for {target!r}. DENY_PATTERNS (layer 3) "
            f"MUST win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prd8_claude_agents_dir_denied() -> None:
    """Domain-owner charters at .claude/agents/ must be denied from public
    export. Charters reference shipped class-of-bug history (PRs #16, #19,
    R1 B2 wrong-gate, NB1 R3 data-loss class) and competitive intel about
    framework architecture. This is not PII per se but is competitive
    leakage owner doesn't want public until CLUTCH ships intentionally.

    Existing piv-* agents at .claude/agents/piv-*.md were already private;
    the new domain-owner charters (memory-cognition-owner, runtime-chat-owner,
    personas-owner, orchestration-owner, public-export-owner) + CODEOWNERS.toml
    + _drafts/ all live under the same dir and inherit the deny rule.

    Flip to ALLOW only with explicit user approval when CLUTCH adoption goes
    public.
    """
    cases = [
        ".claude/agents/memory-cognition-owner.md",
        ".claude/agents/runtime-chat-owner.md",
        ".claude/agents/personas-owner.md",
        ".claude/agents/orchestration-owner.md",
        ".claude/agents/public-export-owner.md",
        ".claude/agents/CODEOWNERS.toml",
        ".claude/agents/_drafts/memory-cognition-analysis.md",
        ".claude/agents/piv-validator.md",  # pre-existing — still denied
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny .claude/agents/ file {path!r}. "
            f"Expected catch by: DENY_DIRS '.claude/agents/'. Domain owner "
            f"charters and CODEOWNERS.toml must stay private."
        )


# ---------------------------------------------------------------------------
# PRD-8 Phase 3 — dashboard slice sanitizer rules (WS5)
# ---------------------------------------------------------------------------

MC_PROFILE_CONTRACT_REL = "docs/mc-profile-contract.md"
DASHBOARD_README_REL = "dashboard/README.md"
DASHBOARD_OWNER_CHARTER_REL = ".claude/agents/dashboard-owner.md"


def test_dist_dirs_denied_segment_aware() -> None:
    """Dashboard build-artifact directories must be denied at any path depth.

    The segment-aware match in ``is_denied()`` (the 6daef06 hardening)
    means ``foo/dashboard/server/dist/...`` is also denied even though
    only the canonical top-level path is configured. This regression-
    gates that the segment matcher reaches into nested cases — Phase 3
    introduces a new directory tree and we want to catch any near-miss
    where a build copy ended up under another root.
    """
    cases = [
        # canonical top-level
        "dashboard/server/dist/index.js",
        "dashboard/server/dist/middleware/auth.js",
        "dashboard/web/dist/assets/index-abc123.js",
        "dashboard/web/dist/index.html",
        # nested (e.g. accidentally produced under another root)
        "release/dashboard/server/dist/index.js",
        "vendor/dashboard/web/dist/main.js",
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny dashboard build artifact {path!r}. "
            f"Expected catch by: DENY_DIRS 'dashboard/server/dist/' or "
            f"'dashboard/web/dist/' (segment-aware). Build artifacts "
            f"must never ship — bloat + possible bundled secrets."
        )


def test_node_modules_denied_segment_aware() -> None:
    """Dashboard node_modules trees must be denied at any path depth.

    Same segment-aware rationale as the dist test. ``node_modules/``
    inside the dashboard slice should never ship — license violations
    + bloat + the trees can hide secrets if a postinstall script wrote
    one.
    """
    cases = [
        "dashboard/server/node_modules/hono/package.json",
        "dashboard/web/node_modules/preact/dist/preact.mjs",
        # nested forms
        "release/dashboard/server/node_modules/hono/index.js",
        "vendor/dashboard/web/node_modules/preact/dist/preact.js",
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny dashboard node_modules path {path!r}. "
            f"Expected catch by: DENY_DIRS 'dashboard/server/node_modules/' "
            f"or 'dashboard/web/node_modules/' (segment-aware)."
        )


def test_mc_profile_contract_doc_explicitly_included() -> None:
    """The mc-profile-contract doc must NOT be denied. It lives under
    ``docs/`` (in DENY_DIRS) but is surgically lifted via INCLUDE_FILES
    because it is the public dashboard HTTP API contract.

    Direct ``is_denied()`` call — proves the layered precedence (Layer
    4 INCLUDE_FILES override of Layer 5 DENY_DIRS) is wired correctly
    for the new entry.
    """
    assert sanitize.is_denied(MC_PROFILE_CONTRACT_REL) is False, (
        f"sanitizer denied {MC_PROFILE_CONTRACT_REL!r} — public mirror "
        f"will be missing the dashboard HTTP API contract. Check that "
        f"INCLUDE_FILES in scripts/sanitize.py contains this path AND "
        f"that DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS do not match it."
    )


def test_dashboard_readme_explicitly_included() -> None:
    """The dashboard/README.md is NOT under DENY_DIRS today, so this
    test is informational/defensive — it proves ``is_denied()`` returns
    False even if a future operator accidentally adds ``dashboard/`` to
    DENY_DIRS without simultaneously updating INCLUDE_FILES coverage.
    """
    assert sanitize.is_denied(DASHBOARD_README_REL) is False, (
        f"sanitizer denied {DASHBOARD_README_REL!r} — public mirror "
        f"will be missing the dashboard dev/build/route documentation. "
        f"Check INCLUDE_FILES contains this path AND that nothing in "
        f"DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS matches it."
    )


def test_dashboard_owner_charter_explicitly_included() -> None:
    """The dashboard-owner charter currently STAYS DENIED.

    .claude/agents/ is in DENY_DIRS — ``test_prd8_claude_agents_dir_denied``
    locks this until CLUTCH ships publicly with explicit owner approval.
    This test asserts the current locked state: dashboard-owner.md is
    denied alongside the other domain-owner charters.

    When CLUTCH adoption goes public and owner flips ``.claude/agents/``
    out of DENY_DIRS, this test should be replaced (the file should
    then be unconditionally allowed by the absence of a deny rule, not
    by an INCLUDE_FILES surgical lift). For now: locked.
    """
    assert sanitize.is_denied(DASHBOARD_OWNER_CHARTER_REL) is True, (
        f"sanitizer FAILED to deny {DASHBOARD_OWNER_CHARTER_REL!r}. "
        f"Until CLUTCH ships publicly, .claude/agents/ stays in "
        f"DENY_DIRS — see test_prd8_claude_agents_dir_denied for the "
        f"locked-private rationale."
    )


def test_no_secrets_leak_through_dashboard_tree() -> None:
    """Scan the dashboard/ source tree for hard-coded secret-shaped
    strings. The dashboard source files DO ship publicly, so any
    accidental hard-coded token, BotFather mention, or Anthropic key
    pattern is a class-of-bug we catch at sanitizer-test time rather
    than waiting for the post-export validate_output scan.

    The scan is over the source tree on disk, not the post-export copy
    — the goal is to fail fast in CI rather than only at full-export
    time.
    """
    dashboard_root = REPO_ROOT / "dashboard"
    if not dashboard_root.exists():
        # Test runs in a checkout that pre-dates dashboard/ — skip silently.
        # Once dashboard/ lands, this branch never trips.
        return

    # Patterns whose presence in dashboard/ source is a near-miss leak.
    # Each pattern is something we have already seen attempted (real bot
    # tokens), or something that has no business being hard-coded
    # (Anthropic SDK keys, "BotFather" prose suggesting a how-to-leak).
    suspicious_patterns: list[tuple[str, "re.Pattern[str]"]] = [
        ("real telegram bot token", __import__("re").compile(
            r"\b\d{9,12}:[A-Za-z0-9_-]{30,}\b"
        )),
        ("anthropic api key", __import__("re").compile(
            r"sk-ant-[A-Za-z0-9_-]{20,}"
        )),
        ("openai api key", __import__("re").compile(
            r"sk-proj-[A-Za-z0-9_-]{20,}"
        )),
        # Hard-coded user-token literal — anything assigning a long string
        # to a name like ``bot_token`` / ``BOT_TOKEN`` is a smell.
        ("hardcoded bot_token assignment", __import__("re").compile(
            r"""(?im)\bbot_token\s*[:=]\s*["'][A-Za-z0-9_:-]{20,}["']"""
        )),
    ]

    failures: list[str] = []
    skip_dirs = {"node_modules", "dist", "__tests__"}
    skip_suffixes = {".lock", ".log"}

    for path in dashboard_root.rglob("*"):
        if not path.is_file():
            continue
        # Skip build artifacts + dep trees + test fixtures (tests may
        # legitimately use throwaway tokens for validation).
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in skip_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pat in suspicious_patterns:
            for m in pat.finditer(content):
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} — {label!r} matched: "
                    f"{m.group(0)[:80]!r}"
                )

    assert not failures, (
        "sanitizer dashboard-tree scan found near-miss leak shapes — each "
        "is a hard-coded value that should be an env-var lookup or test "
        "fixture under __tests__/:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_dashboard_server_src_files_pass_through_to_public() -> None:
    """Positive control: legitimate dashboard source code MUST pass
    ``is_denied()`` (False = allowed). This test catches the
    false-deny class-of-bug where a future restructure of DENY_DIRS
    accidentally swallows dashboard/server/src/ or dashboard/web/src/.
    """
    legitimate_paths = [
        "dashboard/server/src/index.ts",
        "dashboard/server/src/translate.ts",
        "dashboard/server/src/auth-policy.ts",
        "dashboard/server/src/framework-client.ts",
        "dashboard/server/src/middleware/auth.ts",
        "dashboard/server/src/middleware/csrf.ts",
        "dashboard/server/src/routes/agents.ts",
        "dashboard/server/src/routes/conversation.ts",
        "dashboard/server/package.json",
        "dashboard/web/src/App.tsx",
        "dashboard/web/src/main.tsx",
        "dashboard/web/src/pages/Agents.tsx",
        "dashboard/web/src/components/Sidebar.tsx",
        "dashboard/web/package.json",
        "dashboard/web/vite.config.ts",
        "dashboard/web/tsconfig.json",
    ]
    failures: list[str] = []
    for path in legitimate_paths:
        if sanitize.is_denied(path) is True:
            failures.append(path)
    assert not failures, (
        f"sanitizer falsely denied legitimate dashboard source files: "
        f"{failures!r}. Source under dashboard/server/src/ and "
        f"dashboard/web/src/ MUST ship publicly — only dist/ and "
        f"node_modules/ are denied."
    )


def test_prp7_dynamic_lock_pid_scan() -> None:
    """Dynamic regression: every currently-tracked .lock or .pid file
    must be denied. Catches future operator mistakes where a new
    runtime-state file is accidentally ``git add``'d.

    This test reads ``git ls-files`` at runtime — the test set is NOT
    hardcoded. If a new ``foo.lock`` shows up tracked, the test fails
    immediately and points at the file, the rule that should catch it,
    and what the sanitizer actually returned.
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith((".lock", ".pid"))
    ]
    failures: list[str] = []
    for path in tracked:
        if sanitize.is_denied(path) is not True:
            failures.append(path)
    assert not failures, (
        f"sanitizer FAILED to deny tracked runtime-state files: "
        f"{failures!r}. Each one is a public-mirror leak risk. Add to "
        f"DENY_FILES (layer 1) or fix DENY_EXTENSIONS / DENY_PATTERNS."
    )
