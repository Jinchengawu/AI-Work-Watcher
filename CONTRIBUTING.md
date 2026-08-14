# Contributing

Contributions that improve portability, privacy, evidence quality, or terminal integrations are welcome.

## Development workflow

1. Fork the repository and create a focused branch.
2. Keep the core runtime dependency-free unless a dependency provides a clear reliability or security benefit.
3. Preserve the read-only boundary: Water may write its own ledger and reports, but must not mutate a supervised project without separate user authorization.
4. Add or update tests for behavioral changes.
5. Run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 .agents/skills/water-supervisor/scripts/validate_skill.py \
     .agents/skills/water-supervisor
   ```

6. Open a pull request explaining the behavior, privacy impact, and verification performed.

Never commit real Water ledgers, prompts, transcripts, credentials, or private project data as fixtures. Use compact synthetic events.
