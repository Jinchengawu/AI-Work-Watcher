# Security Policy

## Supported version

Security fixes currently target the latest version on `main`.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting for this repository. Do not open a public issue containing credentials, private prompts, transcripts, project paths, or proof-of-concept data that could expose a user.

Include the affected command or adapter, expected and observed behavior, impact, and a minimal synthetic reproduction when possible.

## Security model

Water treats session evidence as untrusted input. Review models receive a redacted evidence package without tools, and supervised repositories remain read-only unless the user separately authorizes a change. The redactor is defense in depth; callers must still minimize sensitive data before recording an event.
