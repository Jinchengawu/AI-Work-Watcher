# AI-Work-Watcher protocol

AI-Work-Watcher separates model judgment from deterministic local operations. The Skill creates Task Briefs and evidence-backed diagnoses. The CLI validates inputs, stores private records, captures structure hashes, and applies only explicitly approved assets.

The lifecycle is `Prepare → Execute → Finish → Improve`. Prepare is a preview until approval. Finish is structured and content-minimizing. Improve promotes a successful Prompt/workflow or opens a reversible proposal. Trends require three completed tasks and current confirmation.

Every diagnostic dimension cites evidence IDs. Scores remain independent; there is no total score. `unknown` is mandatory when evidence is insufficient. Result-adjusted efficiency is evaluated only after outcome and quality.

Project assets live in `.ai-work-watcher/prompts/` and `.ai-work-watcher/workflows/`. Private task records, snapshots, observations, proposals, trends, and archives live under `~/.ai-work-watcher/`.
