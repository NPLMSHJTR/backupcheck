"""Command-line interface for backupcheck's harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .harness import run
from .report import write_reports

EXIT_OK = 0
EXIT_ERROR = 2


def cmd_run(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    result = run(workdir, files=args.files, seed=args.seed)
    paths = write_reports(result, workdir / "reports")
    print(f"backupcheck {__version__}  {result['files']} files  {result['bytes'] / 1e6:.1f} MB")
    print(
        f"clean tree issues: {result['clean_issues']}  "
        f"full {result['full_ms']} ms  fast {result['fast_ms']} ms"
    )
    for kind, expected in result["expected"].items():
        print(
            f"  {kind:<8} injected {expected:<3} full {result['detected'][kind]:<3} "
            f"fast {result['fast_detected'][kind]:<3} false positives {result['false_positives'][kind]}"
        )
    print(f"report: {paths['report']}")
    print(f"html:   {paths['html']}")
    return EXIT_OK if all(result["checks"].values()) else EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backupcheck", description="Verify a backup tree and measure what fast mode misses."
    )
    parser.add_argument("--version", action="version", version=f"backupcheck {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_cmd = subparsers.add_parser("run", help="build a tree, inject faults, verify")
    run_cmd.add_argument("--files", type=int, default=600)
    run_cmd.add_argument("--seed", type=int, default=7)
    run_cmd.add_argument("--workdir", default="backupcheck-run")
    run_cmd.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, OSError) as error:
        print(f"backupcheck: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
