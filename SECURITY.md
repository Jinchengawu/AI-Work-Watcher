# Security Policy

## Supported version

Security fixes currently target the latest version on `main`.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting for this repository. Do not open a public issue containing credentials, private prompts, transcripts, project paths, or proof-of-concept data that could expose a user.

Include the affected command or adapter, expected and observed behavior, impact, and a minimal synthetic reproduction when possible.

## Security model

AI-Work-Watcher treats all task evidence as untrusted input. It never intentionally stores transcripts, complete model responses, source code, diffs, patches, terminal output, or secrets. Private records contain approved Prompts, Task Briefs, compact outcomes, verification summaries, numeric metrics, and file-path hashes. Only explicitly registered projects are observed, and project assets change only after the user approves the exact proposal.
