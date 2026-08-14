---
name: ai-work-watcher
description: Prepare, finish, and improve personal Codex CLI or Claude Code work with approved prompts, structured evidence, and privacy-preserving trends.
---

# AI-Work-Watcher

Use this Skill for an explicitly registered personal development project. The Skill performs reasoning; `ai-work-watcher` performs deterministic validation and storage.

## Safety boundary

- Never modify a project file during Prepare.
- Never collect a transcript, full model response, source code, diff, patch, terminal output, or secret.
- Show one concrete proposal and its exact diff before changing a project asset. Apply it only after explicit approval.
- Do not reorganize source directories in this coaching flow. Produce a separate implementation plan.
- Do not call a model in the background. Ask before generating trends.

## Prepare

1. Confirm the project is registered with `ai-work-watcher project list`.
2. Read the original Prompt, README, AGENTS/CLAUDE instructions, manifests, test entry points, architecture documents, relevant Skill files, and the top-level structure. Respect ignore rules.
3. Run `ai-work-watcher project inspect` to record paths, types, hashes, and drift only.
4. Draft a Task Brief with goal, context, constraints, acceptance criteria, unknowns, recommended workflow, and refined Prompt.
5. Present the brief for approval. Until approval, do not write project or private task assets.
6. After approval, submit JSON to `ai-work-watcher task prepare --stdin`. Include `approved: true`, `source`, `raw_session_id`, `original_prompt`, and `task_brief`.

## Execute and Finish

Perform only the approved task. At Finish, summarize outcome, verification evidence, rework reasons, and available numeric metrics: elapsed time, turns, tool calls, tokens, or cost.

Diagnose exactly five dimensions: `task_definition`, `context_structure`, `prompt_effectiveness`, `execution_verification`, and `result_adjusted_efficiency`. Each has `score` (1–5 or null), `state`, `confidence`, `evidence_ids`, `diagnosis`, and `next_step`. State mapping: 1 `needs_attention`, 2 `unstable`, 3 `developing`, 4 `healthy`, 5 `repeatable`, null `unknown`. If the outcome was not met, efficiency must be `unknown`.

Submit JSON to `ai-work-watcher task finish --stdin`. Offer at most one immediate improvement. If the result says `trend_ready`, ask before generating trends.

## Promote and improve

- Only a successful completed task can promote a Prompt or workflow.
- Show the exact new asset before running `prompt promote ... --approved`. Revisions never overwrite older files.
- A repeating trend needs at least two independent task IDs. Fewer than three completed tasks means no trend conclusion.
- Every project-level improvement needs evidence, expected effect, validation metric, and rollback condition. Later comparable tasks mark it verified or retired.
