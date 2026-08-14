# Contributing

Contributions that improve workflow clarity, privacy, evidence quality, or Codex/Claude Code integration are welcome.

## Development workflow

1. Fork the repository and create a focused branch.
2. Keep the runtime dependency-free unless a dependency clearly improves reliability or security.
3. Preserve approval boundaries: Prepare does not write assets, and project changes require an exact proposal plus explicit approval.
4. Never store real transcripts, complete responses, source code, diffs, terminal output, credentials, or private task history in fixtures.
5. Add behavior tests and run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 .agents/skills/ai-work-watcher/scripts/validate_skill.py .agents/skills/ai-work-watcher
   git diff --check
   ```

6. Open a pull request explaining behavior, privacy impact, and verification.
