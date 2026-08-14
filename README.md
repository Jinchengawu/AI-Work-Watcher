# AI-Work-Watcher

**Turn each AI coding request into a clearer Prompt, a verifiable workflow, and a reusable improvement.**

[简体中文](README.zh-CN.md)

> **Alpha · 0.2.0a1.** Built for individual developers using Codex CLI or Claude Code. Interfaces and local data formats may change before a stable release.

AI-Work-Watcher is a local-first AI workflow coach and Prompt management system. Before a task, its Agent Skill studies your request and project context, then drafts a Task Brief and refined Prompt for approval. After the task, it records compact evidence about outcomes, verification, rework, and result-adjusted efficiency. Over time, it can propose versioned Prompt, workflow, and project-context improvements—without storing transcripts or silently editing your repository.

```text
Prepare             Execute              Finish               Improve
request + context → approved brief → work in Codex/Claude → evidence → reusable asset
```

## Why it exists

AI coding often becomes inefficient for reasons that raw token counts cannot explain: vague goals, missing acceptance criteria, stale project instructions, weak verification, and repeated Prompt repairs. AI-Work-Watcher makes those workflow decisions visible and improvable. Cost remains an optional efficiency signal, and only after the requested outcome and quality bar are met.

## What works in this Alpha

- Prepare an approval-ready Task Brief with goal, context, constraints, acceptance criteria, unknowns, recommended workflow, and refined Prompt.
- Record structured Finish evidence without complete responses, transcripts, source code, diffs, patches, or terminal output.
- Track five independent dimensions—task definition, context structure, Prompt effectiveness, execution and verification, and result-adjusted efficiency—with evidence IDs and no total score.
- Capture key project paths, types, and hashes to detect context drift while excluding common secrets, dependency trees, and generated output.
- Promote successful Prompts and workflows into immutable project revisions under `.ai-work-watcher/`.
- Gate trends behind three completed tasks and explicit current-session confirmation.
- Install the same Skill and low-confidence SessionEnd fallback for Codex CLI and Claude Code.
- Archive legacy v0 data without translating its old scores into the new model.

## Install

Requirements: macOS, Python 3.9–3.13, and at least one of Codex CLI or Claude Code.

```bash
git clone https://github.com/Jinchengawu/AI-Work-Watcher.git
cd AI-Work-Watcher
python3 -m pip install -e .
ai-work-watcher install
ai-work-watcher doctor
```

`install` adds user-level Skill links, bootstrap instructions, and SessionEnd hooks. It does not install a weekly scheduler or start background model calls. `doctor` reports Codex and Claude Code separately; an unavailable host is shown as skipped.

## First success

Registering is explicit. A parent or unrelated repository is not monitored automatically.

```bash
cd /path/to/your-project
ai-work-watcher project add . --name my-project
```

Then start Codex CLI or Claude Code in that project and ask:

```text
Use $ai-work-watcher to prepare this task:
Add CSV export. Keep the existing JSON format unchanged.
```

The Skill will inspect project guidance and test entry points, identify missing acceptance criteria, and show a Task Brief plus refined Prompt. Nothing is recorded and no project file is changed until you approve the brief. After execution, ask it to finish the task; the deterministic CLI stores the compact record privately.

## The coaching model

Each Finish diagnosis contains `score: 1–5 | null`, a mapped state, confidence, evidence IDs, diagnosis, and next step.

| Dimension | Question |
| --- | --- |
| `task_definition` | Were the goal, constraints, and acceptance criteria clear? |
| `context_structure` | Did the Prompt match the repository structure, instructions, and current state? |
| `prompt_effectiveness` | Did the Prompt reduce ambiguity and move execution forward? |
| `execution_verification` | Were the workflow, order of operations, and checks complete? |
| `result_adjusted_efficiency` | After outcome and quality, were rework, time, turns, tokens, and cost reasonable? |

Scores map to `needs_attention`, `unstable`, `developing`, `healthy`, and `repeatable`; insufficient evidence is `unknown`. A failed or low-quality task cannot earn a favorable efficiency diagnosis merely by being cheap.

## Commands

```text
ai-work-watcher install | uninstall | doctor
ai-work-watcher project add | remove | list | inspect
ai-work-watcher task prepare | finish --stdin
ai-work-watcher prompt list | show | promote | archive
ai-work-watcher trends generate --stdin
ai-work-watcher proposal accept | reject | verify
ai-work-watcher migrate legacy-v0
ai-work-watcher prune
```

The Agent Skill is the intended interface for Prepare, Finish, and trend reasoning. The CLI validates and stores already-approved structured input; it is not a background analyst.

## Data and approval boundaries

Private data lives under `~/.ai-work-watcher/`: configuration, approved Task Briefs and Prompts, compact task outcomes, structure snapshots, observations, proposals, trend reports, and migration archives. Shareable, approved assets live in the project:

```text
.ai-work-watcher/
├── project.md
├── prompts/
│   ├── index.json
│   └── <name>-r<N>.md
└── workflows/
    ├── index.json
    └── <name>-r<N>.md
```

The Alpha does not store full model replies, transcripts, source code, diffs, patches, terminal output, or secrets. Project-level changes require a concrete proposal and explicit approval. Source-directory reorganization is outside the coaching flow; AI-Work-Watcher can only propose a separate implementation plan.

See [the protocol](docs/protocol.md), [evaluation scope](docs/evaluation.md), and [security policy](SECURITY.md).

## Current limits

- Individual developers only; no team permissions, employee evaluation, or management dashboard.
- Codex CLI and Claude Code only; other agent hosts are not yet supported.
- No Web UI, hosted service, release automation, or default background analysis.
- Trend quality depends on at least three completed tasks and honest structured evidence.
- Alpha migration preserves old data as an archive but does not convert legacy scoring.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 .agents/skills/ai-work-watcher/scripts/validate_skill.py .agents/skills/ai-work-watcher
git diff --check
```

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
