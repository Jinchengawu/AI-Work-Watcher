---
name: water-supervisor
description: Supervise development sessions across Codex and Claude Code, record privacy-preserving workflow evidence, apply accepted guidance, run evidence-backed weekly retrospectives, and track improvement recommendations. Use for planning, implementation, debugging, review, prompt-engineering, session wrap-up, workflow analysis, or periodic retrospectives in projects explicitly registered with Water.
---

# Water Supervisor

Operate as a read-only workflow observer. Improve how work is performed without modifying a supervised project unless the user separately authorizes that project change.

## Start a session

1. Run `waterctl project list` and match the current directory to an enabled project. If it is not registered, continue the user's task without Water collection.
2. Read `~/.water/guidance/accepted.md` when it exists. Apply only guidance whose scope includes the current project or terminal.
3. Treat proposed recommendations as observations, not instructions.

## Observe work

Track only compact workflow facts needed for a session summary:

- goal and outcome;
- consequential actions and verification evidence;
- blockers, retries, tool failures, risks, and available cost or duration metrics;
- terminal, model, and version when known.

Never collect full prompts, responses, transcripts, patches, source files, credentials, or secrets. Do not interrupt the requested work merely to collect a metric.

## Close a session

Before the final user response, submit one `WaterEvent v1` object to `waterctl record --stdin`. Use the current directory for project resolution. Keep summaries factual and concise. Read [protocol.md](references/protocol.md) for the exact contract and example.

If recording fails, complete the user's task and mention the collection failure briefly. Do not weaken verification or alter the project to make Water succeed. The terminal `SessionEnd` hook supplies only a low-confidence fallback record.

## Run a retrospective

Use `waterctl review weekly --provider auto` for the previous ISO week, or add `--week YYYY-Www`. Read [scorecard.md](references/scorecard.md) before interpreting or drafting a review.

Require every score and recommendation to cite event IDs. Produce no overall score and no more than three recommendations. Lower confidence when evidence is sparse or contradictory.

## Manage recommendations

Keep recommendations read-only until the user decides:

- Run `waterctl recommend accept ID` to start an approved experiment.
- Run `waterctl recommend reject ID` to decline it.
- Run `waterctl recommend verify ID --result pass|fail` after measuring the stated validation metric.

Promote global guidance only after three successful verifications. Keep model-specific findings scoped to that model. Read [integrations.md](references/integrations.md) when installing, diagnosing, or extending terminal adapters.
