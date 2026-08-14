# Closed-loop evaluation — 2026-08-14

This evaluation exercised AI Work Watcher locally with real Codex and Claude Code reviewer processes. Personal Water data and full provider output were kept outside the repository; the evidence below contains only aggregate results and synthetic/controlled session summaries.

## Environment

- macOS, Python 3.9.6
- Codex CLI 0.147.0-alpha.6.5
- Claude Code 2.1.181
- Two explicitly registered test projects
- Local JSONL ledgers, no database or background daemon

## Scenarios exercised

1. Registered projects through canonical paths, nested paths, and symlinks.
2. Recorded structured Codex and Claude events into separate project ledgers.
3. Verified session-ID hashing, credential redaction, transcript-shaped input rejection, event deduplication, and concurrent writes.
4. Ran live Codex weekly reviews and checked evidence traceability, score shape, recommendation limits, scopes, and leak indicators.
5. Accepted project guidance and confirmed immediate project-scoped activation.
6. Accepted global guidance and confirmed it remained inactive until the third successful verification.
7. Added closure evidence and reran the review to test whether recommendations adapted.
8. Ran a live Claude Code weekly review across two projects using the same core review schema.
9. Published the repository and executed the clean GitHub Actions matrix.

## Results

- All 18 local automated tests passed on the machine's actual Python 3.9 runtime.
- GitHub Actions passed on Python 3.9, 3.10, 3.11, 3.12, and 3.13.
- Codex generated schema-valid reports with real evidence IDs and machine-checkable project/global scopes.
- Claude Code generated a valid cross-project report after provider-specific transport normalization; the report remained subject to the same strict Water validation.
- Two project events remained in separate JSONL files, and the controlled leak scan found no prohibited fixture strings.
- Project guidance activated after explicit acceptance. Global guidance stayed inactive after acceptance and after two successful checks, then activated on the third.
- After closure evidence was added, Codex stopped repeating the resolved live-review and CI gaps. Correctness and verification scores moved from 4/5 to 5/5, while resource cost dropped to 3/5 because token, duration, and monetary metrics were absent. This is the desired adaptive behavior: stronger evidence raises the relevant dimensions, and missing evidence remains visible rather than being inferred away.

## Defects found by the live loop

The live exercise found issues that the initial unit suite did not expose:

- A failed model validation left the invalid result object populated, which could allow later processing to continue. The provider loop now clears invalid results before fallback or failure.
- Recommendation scope was initially free text, causing ambiguous scopes to be treated as project guidance. Scopes are now restricted to `global`, `project:<id>`, `terminal:<name>`, or `model:<id>`.
- The package declared Python 3.11+, while the actual installed CLI used Python 3.9. The declared and CI-tested floor is now Python 3.9.
- Claude Code sometimes returns schema-compliant JSON in its `result` field rather than `structured_output`, represents display-only cross-project patterns as objects, or uses a small set of enum synonyms. The adapter now accepts only strict JSON, applies a closed deterministic normalization table, and then runs the full Water validator. Unknown shapes still fail closed.
- The first remote CI run depended on locally available Codex/Claude executables in a doctor test. The test now isolates those dependencies explicitly and passes from a clean runner.

## Observed quality and cost

Codex reviews completed in roughly 30–40 seconds in this sample. Claude Code was slower and more variable; one diagnostic attempt took 118 seconds and reported approximately USD 0.183. Claude review calls are capped at USD 0.50. These are observations from a small sample, not a benchmark.

The reports were useful because recommendations included evidence IDs, a concrete change, validation metric, confidence, effort, and rollback condition. The strongest recommendations correctly focused on live-provider coverage, cross-project isolation, CI proof, and missing cost telemetry.

## Remaining limits

- The scheduled Monday LaunchAgent is loaded and its calendar trigger is registered, but this evaluation did not wait for a naturally occurring Monday trigger.
- Codex requires the user to trust a new hook through `/hooks` before its first execution.
- The event sample is controlled and small; production confidence requires multiple real projects and several weekly periods.
- Provider latency and cost are not yet written into the Water event schema automatically.
- Claude output normalization intentionally supports only observed, closed variations. Unrecognized provider output is rejected and logged in redacted form.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
waterctl doctor
waterctl review weekly --provider codex --week YYYY-Www
waterctl review weekly --provider claude --week YYYY-Www
```

Use synthetic or minimized events for testing. Never commit a real `~/.water` ledger.
