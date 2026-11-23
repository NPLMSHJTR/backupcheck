# backupcheck

**中文简介** — 逐文件校验备份是否真的可信：对比源目录与备份的路径、大小和 SHA-256，分类缺失、多余、截断与同尺寸篡改。600 个文件、37 MB 的测试集上，四类故障全部检出、零误报；同时公开“只看大小和时间”的快速模式会漏掉什么。

**English** — Verify that a backup is actually a backup: compare paths, sizes, and SHA-256 between a source tree and its copy, and classify missing, extra, truncated, and silently corrupted files. On 600 files and 37 MB, all four fault classes are detected with zero false positives — and the report shows exactly what a size-only fast check would miss.

```console
$ python scripts/demo.py
backupcheck 0.1.0  600 files  37.2 MB
clean tree issues: 0  full 819.5 ms  fast 61.0 ms
  missing  injected 18  full 18  fast 18  false positives 0
  extra    injected 14  full 14  fast 14  false positives 0
  size     injected 10  full 10  fast 10  false positives 0
  content  injected 10  full 10  fast 0   false positives 0
```

## The column that matters

| fault | injected | full mode | fast mode |
| --- | --- | --- | --- |
| missing in backup | 18 | 18 | 18 |
| extra in backup | 14 | 14 | 14 |
| truncated (size changed) | 10 | 10 | 10 |
| same size, different bytes | 10 | 10 | **0** |

Fast mode compares size and timestamp, which is what most sync tools do. It
catches truncation because the size moves. It cannot catch a byte flip that keeps
the size identical — and that is the failure mode that makes a backup worthless
without anyone noticing. Full mode hashes both sides and catches all ten.

The cost is measured too: 819 ms versus 61 ms on 37 MB, a 13× difference. The
report states both numbers so the trade-off is a decision, not a surprise.

## How verification works

1. Walk both trees and record every relative path with size and mtime.
2. Path only in source → missing; path only in backup → extra.
3. Same path, different size → truncated.
4. Same path, same size → hash both sides with SHA-256 in a four-thread pool;
   unequal digests → content mismatch.

Nothing is deleted or modified. The tool only reads.

## Quick start

```bash
python scripts/demo.py          # builds a labelled tree, injects faults, scores
```

Against a real backup:

```bash
javac -d backupcheck-out java/src/backupcheck/*.java
java -Xmx512m -cp backupcheck-out backupcheck.Verify \
  --source /path/to/originals --backup /mnt/backup/copy --out result.json
```

Add `--fast` for the size-and-time-only pass, and `--threads 8` for more hashing
parallelism.

## Limits

- **Read-only, single tree pair.** No restore, no scheduling, no cloud APIs.
- **No metadata comparison.** Permissions, owners, and xattrs are ignored; only
  names, sizes, and bytes are checked.
- **Whole-file hashing.** Every same-size pair is read end to end; on spinning
  disks with millions of files, the fast pass is the practical first filter.
- **Synthetic faults.** Five injected classes, not real-world bit rot or partial
  copies interrupted mid-write.

## Repository layout

```
java/src/backupcheck/Verify.java   tree walk, classification, threaded SHA-256
python/src/backupcheck/harness.py  labelled tree, five fault classes, scoring
python/src/backupcheck/report.py   Markdown and HTML reports
scripts/demo.py                    the whole experiment in one command
```

## Development

```bash
PYTHONPATH=python/src python -m unittest discover -s python/tests -t python/tests -v
cd python && pip install -e ".[dev]" && ruff check . && mypy
```

## License

MIT. See [LICENSE](LICENSE).
