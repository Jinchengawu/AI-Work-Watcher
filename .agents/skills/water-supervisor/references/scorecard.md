# Water Balanced Scorecard

## Contents

- Scoring rules
- Dimensions
- Recommendation gate
- Adaptation loop

## Scoring rules

Score each dimension independently from 1 to 5. Attach event IDs, a short rationale, and confidence from 0 to 1. Do not calculate an overall score. Use low confidence when fewer than three relevant events exist, evidence conflicts, or outcomes are self-reported without verification.

## Dimensions

| Dimension | Strong evidence |
| --- | --- |
| Delivery correctness | Requested outcome met; regressions and unresolved defects absent |
| Verification discipline | Proportionate tests/checks executed; limitations disclosed |
| Flow efficiency | Low avoidable wait, clear sequencing, quick blocker resolution |
| Rework | Few repeated attempts caused by preventable misunderstanding or weak checks |
| Resource cost | Appropriate turns, tool calls, model use, token/cost where available |
| Safety | Permission boundaries respected; destructive and sensitive actions controlled |

For `rework` and `resource_cost`, a higher score means healthier behavior, not more rework or cost.

## Recommendation gate

Return at most three recommendations. Require each recommendation to contain:

- exact evidence IDs and a root-cause diagnosis;
- exact target scope: `global`, `project:<registered-project-id>`, `terminal:codex`, `terminal:claude`, or `model:<model-id>`;
- a concrete proposed change, optionally an exact prompt/config diff;
- expected effect, impact, confidence, and effort;
- measurable validation and an explicit rollback condition.

Prefer no recommendation over a weakly supported one.

## Adaptation loop

Keep a recommendation `proposed` until a human accepts or rejects it. Treat acceptance as a time-bounded experiment. Mark a failed experiment `retired`. Allow project-specific accepted guidance immediately; require three successful verifications before promoting global guidance.
