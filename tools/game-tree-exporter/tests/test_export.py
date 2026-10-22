"""Synthetic filesystem checks; never touches an installed game."""
import importlib.util
import csv
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("export_game_tree", Path(__file__).resolve().parents[1] / "export_game_tree.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "game"
        self.root.mkdir()
        self.output = self.base / "report"
        (self.root / "readme.txt").write_text("synthetic", encoding="utf-8")

    def test_filters_and_relative_paths(self):
        (self.root / "profiles").mkdir()
        (self.root / "profiles" / "private.json").write_text("{}")
        (self.root / ".env").write_text("synthetic fixture")
        (self.root / "plugin.dll").write_bytes(b"not a dll")
        result = MODULE.export(self.root, self.output)
        self.assertEqual([row["rel_path"] for row in result["items"]], ["readme.txt"])
        self.assertEqual(result["root"], "<selected folder>")
        for path in self.output.iterdir():
            self.assertNotIn(str(self.root), path.read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.output / "game_files.json").read_text())["counts"]["file"], 1)

    def test_output_subtree_is_not_inventoried(self):
        inside = self.root / "reports"
        inside.mkdir()
        (inside / "old.txt").write_text("old report")
        result = MODULE.export(self.root, inside)
        self.assertFalse(any(row["rel_path"].startswith("reports") for row in result["items"]))

    def test_existing_reports_require_overwrite(self):
        MODULE.export(self.root, self.output)
        before = (self.output / "game_files.json").read_bytes()
        with self.assertRaises(ValueError):
            MODULE.export(self.root, self.output)
        self.assertEqual((self.output / "game_files.json").read_bytes(), before)
        MODULE.export(self.root, self.output, overwrite=True)

    def test_skipped_names_can_be_listed_without_expansion(self):
        (self.root / "saves").mkdir()
        (self.root / "saves" / "campaign.txt").write_text("synthetic")
        result = MODULE.export(self.root, self.output, include_skipped=True)
        entries = {row["rel_path"]: row for row in result["items"]}
        self.assertTrue(entries["saves"]["skipped"])
        self.assertNotIn("saves/campaign.txt", entries)

    def test_symlink_is_never_expanded(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.txt").write_text("synthetic")
        try:
            (self.root / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable for this account")
        result = MODULE.export(self.root, self.output, include_skipped=True)
        entries = {row["rel_path"]: row for row in result["items"]}
        self.assertEqual(entries["linked"]["type"], "link")
        self.assertNotIn("linked/private.txt", entries)

    def test_invalid_root_and_output(self):
        with self.assertRaises(ValueError):
            MODULE.export(self.root, self.root)
        with self.assertRaises(ValueError):
            MODULE.export(self.root / "readme.txt", self.output)
        with self.assertRaises(ValueError):
            MODULE.export(self.root, self.output, max_size=-1)

    @unittest.skipUnless(os.name == "nt", "Windows junction check")
    def test_windows_junction_and_linked_output(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.txt").write_text("synthetic")
        junction = self.root / "junction"
        created = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                                 capture_output=True, text=True)
        if created.returncode:
            self.skipTest("Junction creation unavailable")
        result = MODULE.export(self.root, self.output, include_skipped=True)
        entries = {row["rel_path"]: row for row in result["items"]}
        self.assertEqual(entries["junction"]["type"], "link")
        self.assertNotIn("junction/private.txt", entries)
        with self.assertRaises(ValueError):
            MODULE.export(self.root, junction / "reports")
        with self.assertRaises(ValueError):
            MODULE.export(junction, self.base / "other-report")

    def test_maximum_file_size(self):
        result = MODULE.export(self.root, self.output, max_size=0)
        self.assertEqual(result["items"], [])

    def test_csv_filenames_cannot_become_spreadsheet_formulas(self):
        (self.root / "=1+1").write_text("synthetic")
        MODULE.export(self.root, self.output)
        with (self.output / "game_files.csv").open(encoding="utf-8", newline="") as stream:
            rows = {row["name"]: row for row in csv.DictReader(stream)}
        self.assertIn("'=1+1", rows)
        self.assertEqual(rows["'=1+1"]["rel_path"], "'=1+1")
        raw = json.loads((self.output / "game_files.json").read_text(encoding="utf-8"))
        self.assertIn("=1+1", [row["name"] for row in raw["items"]])
        for prefix in ("+", "-", "@", "\t", "\r", "\n", " ="):
            self.assertTrue(MODULE.csv_safe(prefix + "example").startswith("'"))


if __name__ == "__main__":
    unittest.main()
