"""Tests for tree construction and fault injection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backupcheck.harness import build_tree, inject


class HarnessTests(unittest.TestCase):
    def test_tree_has_requested_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_tree(root, files=20, directories=4, seed=1)
            self.assertEqual(len(data["files"]), 20)
            self.assertTrue(all((root / name).is_file() for name in data["files"]))

    def test_injection_produces_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_tree(root, files=60, directories=1, seed=2)
            import shutil

            backup = root / "backup"
            shutil.copytree(root / "dir00", backup / "dir00")
            truth = inject(backup, data["files"], seed=3)
            self.assertTrue(truth["missing"])
            self.assertTrue(truth["size"])
            self.assertTrue(truth["content"])
            self.assertTrue(truth["extra"])


if __name__ == "__main__":
    unittest.main()
