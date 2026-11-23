"""Corruption matrix and scoring for backupcheck.

The harness builds a source tree, copies it, then damages the copy in five known
ways. Every issue the verifier reports is compared with that ground truth, so the
claim "it detects corruption" is measured per kind instead of asserted.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CLASSES = ROOT / "backupcheck-out"


def compile_java() -> None:
    sources = sorted(str(path) for path in (ROOT / "java" / "src" / "backupcheck").glob("*.java"))
    subprocess.run(["javac", "-d", str(CLASSES), *sources], check=True, capture_output=True)


def build_tree(root: Path, files: int = 600, directories: int = 20, seed: int = 7) -> dict[str, Any]:
    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for index in range(files):
        directory = root / f"dir{index % directories:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        size = rng.randint(2_000, 120_000)
        payload = bytes(rng.randrange(256) for _ in range(min(size, 8_000)))
        payload = (payload * (size // len(payload) + 1))[:size]
        path = directory / f"file{index:04d}.bin"
        path.write_bytes(payload)
        names.append(path.relative_to(root).as_posix())
    return {"files": names, "bytes": sum((root / name).stat().st_size for name in names)}


def run_verify(source: Path, backup: Path, workdir: Path, fast: bool = False) -> dict[str, Any]:
    out = workdir / ("fast.json" if fast else "full.json")
    arguments = [
        "java",
        "-Xmx512m",
        "-cp",
        str(CLASSES),
        "backupcheck.Verify",
        "--source",
        str(source),
        "--backup",
        str(backup),
        "--out",
        str(out),
    ]
    if fast:
        arguments.append("--fast")
    subprocess.run(arguments, check=True, capture_output=True, text=True)
    payload: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return payload


def inject(backup: Path, names: list[str], seed: int = 11) -> dict[str, set[str]]:
    rng = random.Random(seed)
    shuffled = names[:]
    rng.shuffle(shuffled)
    truth: dict[str, set[str]] = {"missing": set(), "extra": set(), "size": set(), "content": set()}

    for name in shuffled[:12]:
        (backup / name).unlink()
        truth["missing"].add(name)
    for name in shuffled[12:22]:
        path = backup / name
        path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
        truth["size"].add(name)
    for name in shuffled[22:32]:
        path = backup / name
        data = bytearray(path.read_bytes())
        position = len(data) // 2
        data[position] ^= 0xFF
        path.write_bytes(bytes(data))
        truth["content"].add(name)
    for index in range(8):
        name = f"extra/added{index:02d}.bin"
        path = backup / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not in the source tree" * 100)
        truth["extra"].add(name)
    for name in shuffled[32:38]:
        parts = name.split("/")
        target = f"{parts[0]}/renamed-{parts[-1]}"
        (backup / name).rename(backup / target)
        truth["missing"].add(name)
        truth["extra"].add(target)
    return truth


def issue_keys(payload: dict[str, Any]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {"missing": set(), "extra": set(), "size": set(), "content": set()}
    for issue in payload["issues"]:
        grouped.setdefault(issue["kind"], set()).add(issue["path"])
    return grouped


def run(workdir: Path, files: int = 600, seed: int = 7) -> dict[str, Any]:
    compile_java()
    source = workdir / "source"
    clean_backup = workdir / "backup-clean"
    dirty_backup = workdir / "backup-dirty"
    for path in (source, clean_backup, dirty_backup):
        if path.exists():
            shutil.rmtree(path)
    built = build_tree(source, files=files, seed=seed)
    shutil.copytree(source, clean_backup, copy_function=shutil.copy2)
    shutil.copytree(source, dirty_backup, copy_function=shutil.copy2)

    clean = run_verify(source, clean_backup, workdir)
    truth = inject(dirty_backup, built["files"])
    full = run_verify(source, dirty_backup, workdir)
    fast = run_verify(source, dirty_backup, workdir, fast=True)

    full_issues = issue_keys(full)
    fast_issues = issue_keys(fast)
    detected = {kind: len(full_issues[kind] & truth[kind]) for kind in truth}
    false_positives = {kind: len(full_issues[kind] - truth[kind]) for kind in truth}
    fast_detected = {kind: len(fast_issues[kind] & truth[kind]) for kind in truth}

    return {
        "files": built["files"].__len__(),
        "bytes": built["bytes"],
        "clean_issues": len(clean["issues"]),
        "full_ms": full["ms"],
        "fast_ms": fast["ms"],
        "hashed": full["hashed"],
        "expected": {kind: len(values) for kind, values in truth.items()},
        "detected": detected,
        "false_positives": false_positives,
        "fast_detected": fast_detected,
        "issues": full["issues"],
        "checks": {
            "clean_tree_has_no_issues": len(clean["issues"]) == 0,
            "all_injected_faults_detected": all(detected[kind] == len(truth[kind]) for kind in truth),
            "no_false_positives": all(value == 0 for value in false_positives.values()),
        },
    }
