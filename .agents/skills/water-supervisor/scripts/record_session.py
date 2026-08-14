#!/usr/bin/env python3
"""Forward a WaterEvent JSON object from stdin to the canonical CLI."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[4]
raise SystemExit(subprocess.run([str(root / "bin" / "waterctl"), "record", "--stdin"], stdin=sys.stdin).returncode)
