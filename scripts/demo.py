#!/usr/bin/env python3
"""Run backupcheck: build a tree, damage a copy, verify, and score."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    missing = [tool for tool in ("javac", "java") if shutil.which(tool) is None]
    if missing:
        print(f"missing required tools: {', '.join(missing)}", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python" / "src")
    command = [sys.executable, "-m", "backupcheck", "run", "--workdir", "backupcheck-run"]
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True, env=env)
    print()
    print(f"report: {ROOT / 'backupcheck-run' / 'reports' / 'report.md'}")
    print(f"html:   {ROOT / 'backupcheck-run' / 'reports' / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
