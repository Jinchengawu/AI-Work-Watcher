#!/usr/bin/env python3
"""Dependency-free structural validation for the distributable Water Skill."""

from pathlib import Path
import re
import sys


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    skill = path / "SKILL.md"
    if not skill.is_file():
        return ["SKILL.md is missing"]
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return ["SKILL.md must start with YAML frontmatter"]
    frontmatter = match.group(1)
    fields = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    if set(fields) != {"name", "description"}:
        errors.append("frontmatter must contain only name and description")
    if fields.get("name") != path.name or not re.fullmatch(r"[a-z0-9-]{1,63}", fields.get("name", "")):
        errors.append("skill name must match its lowercase hyphenated directory")
    if not fields.get("description"):
        errors.append("description is required")
    if not (path / "agents" / "openai.yaml").is_file():
        errors.append("agents/openai.yaml is missing")
    for reference in re.findall(r"\]\((references/[^)]+)\)", text):
        if not (path / reference).is_file():
            errors.append(f"missing reference: {reference}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_skill.py PATH", file=sys.stderr)
        return 2
    errors = validate(Path(sys.argv[1]))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
