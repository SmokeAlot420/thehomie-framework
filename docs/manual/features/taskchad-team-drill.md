# TaskChad Team Drill

Status: deterministic and runtime modes shipped; runtime mode live-proven
Owner: Python orchestration
Last updated: 2026-05-31

## What It Does

TaskChad Team Drill runs a bounded multi-role drill around TaskChad growth. It
creates a team/convoy, runs Sales, Marketing, Product/Ops, reviewer, and final
synthesis turns, and can optionally execute role turns through real runtime
lanes.

## Operator Entry Points

- Chat/Telegram: `/taskchaddrill [--runtime] [--lane <lane>] [--target-url <url>]`
- Dashboard: `/teams` TaskChad drill controls/result panel
- API: `/api/team/taskchad-drill`
- CLI: `thehomie chat -q "/taskchaddrill ..."`

## Source Of Truth Files

| Layer | Files |
|---|---|
| Python/runtime | `.claude/scripts/orchestration/team_drill.py`, `.claude/scripts/orchestration/team_loop.py` |
| Chat/router | `.claude/chat/core_handlers.py`, `.claude/chat/router.py`, `.claude/chat/commands.py` |
| Dashboard/API | `.claude/scripts/orchestration/api.py`, `dashboard/web/src/pages/Teams.tsx`, `dashboard/server/src/routes.ts` |
| Tests | `.claude/scripts/tests/test_team_drill.py`, `.claude/scripts/tests/test_taskchad_drill_command.py`, `.claude/scripts/tests/test_team_loop.py`, `.claude/scripts/tests/test_router_transcript_persistence.py` |
| Docs/proof | `docs/HANDOFF-taskchad-runtime-mode-drill-closeout-2026-05-29.md`, `docs/HANDOFF-taskchad-team-drill-2026-05-27.md` |

## Safety Boundaries

- Deterministic/no-runtime mode remains the default.
- Runtime mode is explicit via `--runtime`.
- Runtime role turns keep `allowed_tools=[]` and `disallowed_tools=["*"]`.
- Sanitized payloads must not expose prompts, runtime session IDs, claimed
  mailbox bodies, cookies, tokens, or private browser state.
- The safe target URL can be shown, but do not leak arbitrary private URLs.

## How To Run It

Deterministic:

```powershell
cd C:\Users\YourUser\thehomie\.claude\scripts
uv run thehomie chat -q "/taskchaddrill" -Q
```

Runtime-backed:

```powershell
cd C:\Users\YourUser\thehomie\.claude\scripts
uv run thehomie chat -q "/taskchaddrill --runtime --lane generic_runtime" -Q
```

## How To Test It

```powershell
cd C:\Users\YourUser\thehomie\.claude\scripts
uv run python -m py_compile ../chat/core_handlers.py ../chat/router.py orchestration/team_drill.py orchestration/team_loop.py tests/test_team_drill.py tests/test_taskchad_drill_command.py tests/test_router_transcript_persistence.py tests/test_team_loop.py
uv run pytest tests/test_team_drill.py tests/test_taskchad_drill_command.py tests/test_team_loop.py tests/test_router_transcript_persistence.py tests/test_lane_router.py tests/test_runtime_routing.py -q
```

## Latest Live Proof

- Date: 2026-05-29
- Surface: Telegram Web to `@YourBot`
- Command: `/taskchaddrill --runtime --lane generic_runtime`
- Result: team `#15`, convoy `#25`, progress `10/10`, runtime on,
  lane `generic_runtime`, provider `openai-codex`, model `gpt-5.5`, tools `0`,
  elapsed `251001ms`.

## Related Handoffs

- `docs/HANDOFF-taskchad-runtime-mode-drill-closeout-2026-05-29.md`
- `docs/HANDOFF-taskchad-runtime-mode-drill-2026-05-29.md`
- `docs/HANDOFF-taskchad-team-drill-2026-05-27.md`

## Public Export Status

Runtime-mode drill closeout did not public-export in that slice.

## Next Slices

- Runtime-turn observability in the dashboard.
- Deeper TaskChad growth drill presets after Team Room V3 artifact panels.
