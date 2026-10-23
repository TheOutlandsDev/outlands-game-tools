"""Publication gate regressions using synthetic source trees."""
import importlib.util
import copy
import json
import tempfile
import unittest
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("source_release", ROOT / "tools" / "verify_source_release.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-gate-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
        (self.root / "tool.py").write_text("print('synthetic')\n")

    def inventory(self, *, varied_names=False):
        if varied_names:
            (self.root / "docs").mkdir()
            (self.root / "docs/FAQ.md").write_text("# Original toy documentation\n")
            (self.root / "alpha.py").write_text("pass\n")
            (self.root / "Zebra.py").write_text("pass\n")
        MODULE.verify(self.root, True)
        return json.loads((self.root / MODULE.MANIFEST).read_text())

    def write_inventory(self, value):
        (self.root / MODULE.MANIFEST).write_text(json.dumps(value) + "\n", encoding="utf-8")

    def test_new_inventory_has_platform_independent_relative_path_order(self):
        value = self.inventory(varied_names=True)
        paths = [row["path"] for row in value["files"]]
        self.assertEqual(sorted(paths), paths)
        self.assertNotEqual(sorted(paths, key=PureWindowsPath), paths)

    def test_reversed_legacy_records_pass_without_rewriting_manifest(self):
        value = self.inventory(varied_names=True)
        value["files"].reverse()
        self.write_inventory(value)
        before = (self.root / MODULE.MANIFEST).read_bytes()
        self.assertEqual("PASS", MODULE.verify(self.root)["status"])
        self.assertEqual(before, (self.root / MODULE.MANIFEST).read_bytes())

    def test_shuffled_legacy_records_pass_without_rewriting_manifest(self):
        value = self.inventory(varied_names=True)
        value["files"] = value["files"][2:] + value["files"][:2]
        self.write_inventory(value)
        before = (self.root / MODULE.MANIFEST).read_bytes()
        self.assertEqual("PASS", MODULE.verify(self.root)["status"])
        self.assertEqual(before, (self.root / MODULE.MANIFEST).read_bytes())

    def test_windows_ordered_legacy_inventory_passes_on_any_host(self):
        value = self.inventory(varied_names=True)
        value["files"].sort(key=lambda row: PureWindowsPath(row["path"]))
        self.write_inventory(value)
        self.assertEqual("PASS", MODULE.verify(self.root)["status"])

    def test_identical_duplicate_inventory_path_is_refused(self):
        value = self.inventory()
        value["files"].append(dict(value["files"][0]))
        self.write_inventory(value)
        with self.assertRaisesRegex(ValueError, "Duplicate source inventory path"):
            MODULE.verify(self.root)

    def test_conflicting_duplicate_inventory_path_is_refused(self):
        value = self.inventory()
        value["files"].append(dict(value["files"][0], sha256="0" * 64))
        self.write_inventory(value)
        with self.assertRaisesRegex(ValueError, "Duplicate source inventory path"):
            MODULE.verify(self.root)

    def test_changed_inventory_hash_is_refused(self):
        value = self.inventory()
        digest = value["files"][0]["sha256"]
        value["files"][0]["sha256"] = ("1" if digest[0] != "1" else "0") + digest[1:]
        self.write_inventory(value)
        with self.assertRaisesRegex(ValueError, "Source inventory differs"):
            MODULE.verify(self.root)

    def test_changed_inventory_byte_count_is_refused(self):
        value = self.inventory()
        value["files"][0]["bytes"] += 1
        self.write_inventory(value)
        with self.assertRaisesRegex(ValueError, "Source inventory differs"):
            MODULE.verify(self.root)

    def test_inventory_byte_counts_are_exact_bounded_integers(self):
        original = self.inventory()
        length = original["files"][0]["bytes"]
        for invalid in (True, float(length), length + 0.5, str(length), -1, 2 ** 53 + 1):
            with self.subTest(value=invalid):
                value = copy.deepcopy(original)
                value["files"][0]["bytes"] = invalid
                self.write_inventory(value)
                with self.assertRaisesRegex(ValueError, "Invalid source inventory record"):
                    MODULE.verify(self.root)

    def test_invalid_inventory_top_level_schema_is_refused(self):
        original = self.inventory()
        for field, invalid in (("schema_version", True), ("schema_version", 2),
                               ("license", None), ("files", {}), ("unexpected", 1)):
            with self.subTest(field=field, value=invalid):
                value = copy.deepcopy(original)
                value[field] = invalid
                self.write_inventory(value)
                with self.assertRaisesRegex(ValueError, "Invalid source inventory schema"):
                    MODULE.verify(self.root)

    def test_invalid_inventory_record_schema_is_refused(self):
        original = self.inventory()
        for field, invalid in (("path", None), ("path", ""), ("bytes", None),
                               ("sha256", "a" * 63), ("sha256", "A" * 64),
                               ("sha256", None), ("unexpected", 1)):
            with self.subTest(field=field):
                value = copy.deepcopy(original)
                value["files"][0][field] = invalid
                self.write_inventory(value)
                with self.assertRaisesRegex(ValueError, "Invalid source inventory record"):
                    MODULE.verify(self.root)

    def test_duplicate_json_fields_are_refused(self):
        value = self.inventory()
        encoded = json.dumps(value).replace('"schema_version": 1',
                                            '"schema_version": 1, "schema_version": 1')
        (self.root / MODULE.MANIFEST).write_text(encoded, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate source inventory JSON field"):
            MODULE.verify(self.root)

    def test_inventory_detects_tampering_and_added_source(self):
        MODULE.verify(self.root, True)
        self.assertEqual(MODULE.verify(self.root)["status"], "PASS")
        (self.root / "tool.py").write_text("print('changed')\n")
        with self.assertRaises(ValueError):
            MODULE.verify(self.root)
        MODULE.verify(self.root, True)
        (self.root / "extra.py").write_text("pass\n")
        with self.assertRaises(ValueError):
            MODULE.verify(self.root)

    def test_binary_and_unexpected_types_are_refused(self):
        (self.root / "tool.py").write_bytes(b"binary\0payload")
        with self.assertRaises(ValueError):
            MODULE.inspect(self.root)
        (self.root / "tool.py").write_text("pass")
        (self.root / "game.dll").write_text("synthetic placeholder")
        with self.assertRaises(ValueError):
            MODULE.inspect(self.root)

    def test_credential_and_personal_path_markers_are_refused(self):
        path = self.root / "tool.py"
        for content in ("gh" + "p_" + "x" * 40, "C:" + chr(92) + "Users" + chr(92) + "synthetic" + chr(92) + "file"):
            path.write_text(content)
            with self.assertRaises(ValueError):
                MODULE.inspect(self.root)

    def test_private_endpoint_refused_but_loopback_permitted(self):
        path = self.root / "tool.py"
        path.write_text("endpoint = '" + "192.168." + "1.15'\n")
        with self.assertRaises(ValueError):
            MODULE.inspect(self.root)
        path.write_text("endpoint = '127.0.0.1'\n")
        MODULE.inspect(self.root)

    def test_ignored_build_output_is_not_part_of_release(self):
        (self.root / "bin").mkdir()
        (self.root / "bin" / "game.dll").write_bytes(b"not distributed")
        self.assertNotIn("bin/game.dll", [row["path"] for row in MODULE.inspect(self.root)])

    def test_only_reviewed_requirements_path_is_allowed(self):
        for relative, content in (("tools/lua-syntax-checker/requirements.txt", "lupa==2.8\n"),
                                  ("tools/audio-integrity-checker/requirements.txt",
                                   "soundfile==0.13.1\nnumpy==2.2.6\n")):
            requirements = self.root / relative
            requirements.parent.mkdir(parents=True)
            requirements.write_text(content, encoding="utf-8")
            self.assertIn(relative, [row["path"] for row in MODULE.inspect(self.root)])
        (self.root / "unreviewed.txt").write_text("not publication source")
        with self.assertRaises(ValueError):
            MODULE.inspect(self.root)

    def test_virtual_environment_payload_is_not_published(self):
        payload = self.root / "tools/lua-syntax-checker/.venv/Lib/lupa.pyd"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"not distributed\0")
        self.assertNotIn("tools/lua-syntax-checker/.venv/Lib/lupa.pyd",
                         [row["path"] for row in MODULE.inspect(self.root)])


if __name__ == "__main__":
    unittest.main()
