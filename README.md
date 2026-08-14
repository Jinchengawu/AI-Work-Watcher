# AI Work Watcher — Water Supervisor

AI Work Watcher is a local-first, model-neutral workflow supervisor for Codex and Claude Code. Its built-in agent, **Water Supervisor**, records compact and redacted development evidence, produces weekly balanced-scorecard reviews, and tracks improvements through human approval and verification.

Water is deliberately read-only toward supervised repositories. It can suggest a prompt, process, or configuration change, but it never applies that change without separate authorization.

## What it does

```text
Codex / Claude Code
        ↓
Session summary → validation → redaction → local JSONL ledger
        ↓
Weekly evidence package → Codex or Claude reviewer
        ↓
Recommendation → human decision → experiment → verified guidance
```

- Supervises only explicitly registered projects.
- Shares one portable Skill between Codex and Claude Code.
- Stores summaries rather than prompts, transcripts, source code, or patches.
- Uses independent scores for correctness, verification, flow, rework, cost, and safety.
- Falls back from Codex to Claude when `--provider auto` is selected.
- Promotes global guidance only after three successful verifications.

## Requirements

- macOS (the v0.1 scheduler uses LaunchAgents)
- Python 3.11 or newer
- Codex CLI and/or Claude Code
- `launchctl` for the weekly schedule

## Quick start

```bash
./bin/waterctl install
waterctl project add /absolute/path/to/project --name my-project
waterctl doctor
```

The installer links the canonical Skill into Codex and Claude Code, merges Water-owned `SessionEnd` hooks, adds marked bootstrap instructions, and schedules a review for Monday 09:00 Asia/Shanghai. It backs up changed configuration files and preserves all non-Water entries. Codex asks you to review and trust newly installed hooks through `/hooks` before their first execution.

Use `--no-schedule` if you only want the Skill and hooks:

```bash
./bin/waterctl install --no-schedule
```

Record a structured session summary:

```bash
waterctl record --stdin <<'JSON'
{
  "source_terminal": "codex",
  "raw_session_id": "local-session-id",
  "goal": "Verify the import workflow",
  "actions": ["Ran the focused test suite"],
  "outcome": "The workflow passed its acceptance tests",
  "status": "completed",
  "evidence": [{"kind": "test", "summary": "12 tests passed"}],
  "blockers": [],
  "risks": [],
  "metrics": {"test_count": 12},
  "tags": ["verification"],
  "confidence": 0.9
}
JSON
```

Run or inspect the weekly loop:

```bash
waterctl review weekly --provider auto
waterctl recommend accept rec-example
waterctl recommend verify rec-example --result pass
```

## Data and privacy

Personal evidence stays under `~/.water/`; it is never written to a supervised repository. Before storage, Water hashes provider session IDs, rejects unknown or transcript-shaped fields, limits text sizes, and redacts credentials, private keys, email addresses, and high-entropy tokens.

The default retention period for session details is 180 days. Weekly reviews and explicitly approved guidance remain until removed. See the [event schema](schemas/water-event-v1.schema.json) and [protocol](.agents/skills/water-supervisor/references/protocol.md) for the exact contract.

## Commands

| Command | Purpose |
| --- | --- |
| `waterctl project add\|remove\|list` | Manage the explicit supervision registry |
| `waterctl record --stdin` | Validate, redact, and append a session summary |
| `waterctl review weekly` | Generate a weekly evidence-backed report |
| `waterctl recommend accept\|reject\|verify` | Manage the improvement lifecycle |
| `waterctl prune` | Enforce event retention |
| `waterctl install\|uninstall\|doctor` | Manage and diagnose terminal integrations |

## Development

The runtime uses only the Python standard library.

```bash
python3 -m unittest discover -s tests -v
python3 .agents/skills/water-supervisor/scripts/validate_skill.py \
  .agents/skills/water-supervisor
```

`waterctl uninstall` preserves personal data by default. Use `waterctl uninstall --purge-data` only when permanent deletion is intended.

## Current boundaries

- v0.1 supports macOS, Codex, and Claude Code.
- There is no web dashboard, cloud sync, team account, database, or full transcript collection.
- Weekly review quality depends on the evidence available and the selected model; low-volume weeks should produce low-confidence findings.

## License

MIT. See [LICENSE](LICENSE).
