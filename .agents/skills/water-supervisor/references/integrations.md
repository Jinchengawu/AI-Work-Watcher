# Terminal Integrations

## Contents

- Shared architecture
- Codex
- Claude Code
- Scheduler
- Extension contract

## Shared architecture

Use one canonical Skill in the Water repository. Install symlinks into each terminal's discovery directory. Add a short global bootstrap marker and a `SessionEnd` command hook. The hook receives lifecycle JSON, resolves only registered projects, and records a fallback without reading the transcript path.

Run `waterctl install`, then `waterctl doctor`. Re-running installation must be idempotent. Existing non-Water hooks and instructions must remain intact.

## Codex

- Skill destination: `~/.agents/skills/water-supervisor`.
- Bootstrap: Water-managed block in `~/.codex/AGENTS.md`.
- Hook: Water-managed `SessionEnd` entry in `~/.codex/hooks.json`.
- Weekly reviewer: `codex exec` with an output schema, ephemeral session, ignored user config/rules, and read-only sandbox.

## Claude Code

- Skill destination: `~/.claude/skills/water-supervisor`.
- Bootstrap: Water-managed block in `~/.claude/CLAUDE.md`.
- Hook: Water-managed `SessionEnd` entry merged into `~/.claude/settings.json`.
- Weekly reviewer: `claude --print` with no tools, no session persistence, and a JSON schema.

## Scheduler

Install `~/Library/LaunchAgents/com.water-supervisor.weekly.plist`. Run every Monday at 09:00 in `Asia/Shanghai`. Set `WATER_INTERNAL_RUN=1` so review sessions cannot recursively enter the evidence ledger.

## Extension contract

Add another terminal by translating its lifecycle payload into the `WaterEvent v1` contract. Keep provider-specific fields out of the core schema. Never make an adapter read full transcripts as a fallback.
