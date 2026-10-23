"""Publication gate regressions using synthetic source trees."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("source_release", ROOT / "tools" / "verify_source_release.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        fixture_root = ROOT / ".audit" / "verify-tests"
        fixture_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixture_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
        (self.root / "tool.py").write_text("print('synthetic')\n")

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

    def test_only_reviewed_text_paths_are_allowed(self):
        for relative, content in (("tools/lua-syntax-checker/requirements.txt", "lupa==2.8\n"),
                                  ("tools/audio-integrity-checker/requirements.txt",
                                   "soundfile==0.13.1\nnumpy==2.2.6\n"),
                                  ("tools/bounded-evidence-manifest-verifier/examples/files/sample.txt",
                                   "synthetic evidence\n")):
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
