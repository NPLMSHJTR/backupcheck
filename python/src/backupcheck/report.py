"""Markdown and HTML reports for backupcheck."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

KIND_LABELS = {
    "missing": "missing in backup",
    "extra": "extra in backup",
    "size": "size mismatch (truncated)",
    "content": "same size, different bytes",
}


def write_reports(result: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = {key: value for key, value in result.items() if key != "issues"}
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    rows = []
    for kind, label in KIND_LABELS.items():
        rows.append(
            f"| {label} | {result['expected'][kind]} | {result['detected'][kind]} | "
            f"{result['fast_detected'][kind]} | {result['false_positives'][kind]} |"
        )
    lines = [
        "# backupcheck report",
        "",
        f"- files: {result['files']:,}",
        f"- source bytes: {result['bytes'] / 1e6:.1f} MB",
        f"- clean tree issues: {result['clean_issues']}",
        f"- full verification: {result['full_ms']} ms ({result['hashed']:,} files hashed)",
        f"- fast verification: {result['fast_ms']} ms",
        "",
        "| fault | injected | detected (full) | detected (fast) | false positives |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        "",
        "## The point of the fast column",
        "",
        "Fast mode compares size and timestamp only, like most sync tools. It catches "
        "truncation because the size changes, and catches nothing else — a byte flip "
        "keeps the size identical. Publishing that column is the difference between "
        "claiming a backup is verified and knowing what was actually checked.",
    ]
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    table = "".join(
        f"<tr><td>{html.escape(KIND_LABELS[kind])}</td><td>{result['expected'][kind]}</td>"
        f"<td>{result['detected'][kind]}</td><td>{result['fast_detected'][kind]}</td>"
        f"<td>{result['false_positives'][kind]}</td></tr>"
        for kind in KIND_LABELS
    )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>backupcheck report</title>
<style>
 body{{margin:0;background:#0b1020;color:#e6ecf6;font:15px/1.6 ui-sans-serif,system-ui,sans-serif}}
 header{{padding:28px 24px;border-bottom:1px solid #26314a}}
 h1{{margin:0 0 6px;font-size:20px}} .sub{{color:#8fa0b8;font-size:13px}}
 .stats{{display:flex;gap:26px;margin-top:16px;flex-wrap:wrap}}
 .stat b{{display:block;font-size:22px}} .stat span{{color:#8fa0b8;font-size:12px}}
 main{{padding:22px 24px}} table{{border-collapse:collapse;width:100%;max-width:820px}}
 th,td{{padding:8px 10px;border-bottom:1px solid #26314a;text-align:left}}
 th{{color:#8fa0b8;font-weight:500}}
</style></head><body>
<header><h1>backupcheck</h1>
<div class="sub">Source tree versus backup · full hash verification</div>
<div class="stats">
 <div class="stat"><b>{result["files"]:,}</b><span>files</span></div>
 <div class="stat"><b>{result["bytes"] / 1e6:.1f} MB</b><span>source size</span></div>
 <div class="stat"><b>{result["full_ms"]} ms</b><span>full verify</span></div>
 <div class="stat"><b>{result["clean_issues"]}</b><span>issues on clean tree</span></div>
</div></header>
<main><table><thead><tr><th>fault</th><th>injected</th><th>detected (full)</th>
<th>detected (fast)</th><th>false positives</th></tr></thead><tbody>{table}</tbody></table></main>
</body></html>
"""
    html_path = out_dir / "report.html"
    html_path.write_text(page, encoding="utf-8")
    return {"report": report_path, "metrics": metrics_path, "html": html_path}
