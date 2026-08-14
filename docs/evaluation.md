# Alpha evaluation

The Alpha evaluation uses behavioral fixtures for Codex CLI and Claude Code.

- Prepare identifies missing acceptance criteria and writes nothing before approval.
- Finish rejects transcript-shaped or code-shaped fields.
- Snapshots detect context additions, removals, and changed hashes while ignoring secrets, dependencies, and generated trees.
- Five diagnoses enforce evidence and score/state mapping; failed outcomes cannot receive an efficiency score.
- Prompt promotion is restricted to successful tasks and creates immutable revisions.
- Trend generation enforces task count, explicit confirmation, and cross-task evidence.
- SessionEnd records only a low-confidence fallback when structured Finish is absent.
- Legacy migration archives old records without translating old scores.

These tests establish protocol behavior, not productivity claims. Real outcome claims require comparable follow-up tasks.
