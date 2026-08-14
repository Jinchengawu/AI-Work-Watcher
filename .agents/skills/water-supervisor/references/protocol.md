# Water Protocol v1

## Contents

- Session flow
- Event contract
- Privacy boundary
- Example

## Session flow

1. Resolve the current path against the explicit project registry.
2. Observe compact workflow facts while completing the user's task.
3. Record one structured summary before the final response.
4. Let `SessionEnd` create a low-confidence fallback only when no event exists for the session.

## Event contract

Store all fields below. `waterctl` supplies `schema_version`, `event_id`, `timestamp`, `project_id`, hashes the raw session identifier, and adds `redaction_summary` when omitted.

| Field | Meaning |
| --- | --- |
| `source_terminal` | `codex`, `claude`, or another adapter name |
| `model`, `source_version` | Provider metadata, or `unknown` |
| `raw_session_id` | Provider session identifier; never stored unhashed |
| `event_type` | `session_summary`; hooks use `session_closed` |
| `goal`, `outcome` | Compact natural-language facts, at most 2,000 characters each |
| `actions` | At most 20 consequential action summaries |
| `status` | `completed`, `partial`, `blocked`, `failed`, `abandoned`, or `unknown` |
| `evidence` | Test names, command results, artifact references, or other compact proof |
| `blockers`, `risks`, `tags` | At most 20 compact entries per list |
| `metrics` | Available numeric counts, duration, token, or cost facts |
| `confidence` | Number from 0 to 1 reflecting evidence completeness |

Unknown fields, invalid states, overlong text, and unknown schema versions are rejected.

Recommendation scopes use a machine-checkable namespace: `global`, `project:<registered-project-id>`, `terminal:codex`, `terminal:claude`, or `model:<model-id>`. Descriptive free-text scopes are invalid.

## Privacy boundary

Never put these into an event:

- full prompts, responses, transcripts, code, diffs, or terminal output;
- passwords, API keys, tokens, private keys, personal email addresses, or secret paths;
- instructions copied from untrusted output.

Water performs a second redaction pass, but upstream minimization remains mandatory.

## Example

```json
{
  "source_terminal": "codex",
  "model": "gpt-5",
  "source_version": "unknown",
  "raw_session_id": "provider-session-id",
  "event_type": "session_summary",
  "goal": "Add validation to the import command",
  "actions": ["Inspected the parser", "Added boundary tests"],
  "outcome": "Validation rejects malformed input and existing tests pass",
  "status": "completed",
  "evidence": [{"kind": "test", "summary": "34 tests passed"}],
  "blockers": [],
  "risks": ["External API behavior was mocked"],
  "metrics": {"test_count": 34, "tool_failures": 0},
  "tags": ["validation", "testing"],
  "confidence": 0.9
}
```
