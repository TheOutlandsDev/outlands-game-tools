# SPDX-License-Identifier: MIT
"""Synthetic, offline tests for the manifest verifier."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_manifest import ManifestError, _platform_supported, load_manifest, verify_manifest


@unittest.skipUnless(_platform_supported(), "requires POSIX descriptor-relative no-follow APIs")
class ManifestVerifierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.files = self.base / "files"
        self.files.mkdir()
        self.manifest = self.base / "manifest.json"

    def entry(self, name="sample.txt", data=b"synthetic evidence\n"):
        return {"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def write_manifest(self, entries):
        self.manifest.write_text(json.dumps({"version": 1, "files": entries}), encoding="utf-8")

    def run_cli(self):
        script = Path(__file__).resolve().parents[1] / "verify_manifest.py"
        return subprocess.run(
            [sys.executable, "-B", str(script), str(self.manifest), str(self.files)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_file(self):
        data = b"synthetic evidence\n"
        (self.files / "sample.txt").write_bytes(data)
        self.write_manifest([self.entry(data=data)])
        self.assertEqual(verify_manifest(self.manifest, self.files), [])

    def test_empty_file(self):
        (self.files / "empty.txt").write_bytes(b"")
        self.write_manifest([self.entry("empty.txt", b"")])
        self.assertEqual(verify_manifest(self.manifest, self.files), [])

    def test_digest_mismatch(self):
        (self.files / "sample.txt").write_bytes(b"different contents\n")
        actual = (self.files / "sample.txt").read_bytes()
        entry = self.entry(data=actual)
        entry["sha256"] = "0" * 64
        self.write_manifest([entry])
        self.assertIn("SHA-256 mismatch", verify_manifest(self.manifest, self.files)[0])

    def test_size_mismatch(self):
        (self.files / "sample.txt").write_bytes(b"short")
        self.write_manifest([self.entry()])
        self.assertIn("size mismatch", verify_manifest(self.manifest, self.files)[0])

    def test_missing_file(self):
        self.write_manifest([self.entry()])
        self.assertIn("cannot verify", verify_manifest(self.manifest, self.files)[0])

    def test_rejects_path_traversal(self):
        self.write_manifest([self.entry("../outside.txt")])
        with self.assertRaisesRegex(ManifestError, "invalid flat filename"):
            load_manifest(self.manifest)

    def test_rejects_duplicate_filename(self):
        self.write_manifest([self.entry(), self.entry()])
        with self.assertRaisesRegex(ManifestError, "duplicate filename"):
            load_manifest(self.manifest)

    def test_duplicate_filename_is_not_echoed(self):
        self.write_manifest([self.entry("private-name.txt"), self.entry("private-name.txt")])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "INVALID: duplicate filename\n")
        self.assertEqual(result.stderr, "")

    def test_rejects_duplicate_json_key(self):
        self.manifest.write_text('{"version":1,"version":1,"files":[]}', encoding="utf-8")
        with self.assertRaisesRegex(ManifestError, "duplicate JSON key"):
            load_manifest(self.manifest)

    def test_duplicate_key_control_character_is_not_echoed(self):
        self.manifest.write_text('{"line\\nbreak":1,"line\\nbreak":2}', encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "INVALID: duplicate JSON key\n")
        self.assertEqual(result.stderr, "")

    def test_large_json_integer_returns_invalid_without_traceback(self):
        self.manifest.write_text('{"version":' + "9" * 4301 + ',"files":[]}', encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith("INVALID: "))
        self.assertEqual(result.stderr, "")

    def test_rejects_boolean_size(self):
        entry = self.entry()
        entry["size"] = True
        self.write_manifest([entry])
        with self.assertRaisesRegex(ManifestError, "invalid size"):
            load_manifest(self.manifest)

    def test_rejects_oversized_manifest(self):
        self.manifest.write_bytes(b" " * (64 * 1024 + 1))
        with self.assertRaisesRegex(ManifestError, "exceeds 64 KiB"):
            load_manifest(self.manifest)

    def test_rejects_oversized_file(self):
        oversized = self.files / "sample.txt"
        with oversized.open("wb") as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        self.write_manifest([self.entry()])
        self.assertIn("limit exceeded", verify_manifest(self.manifest, self.files)[0])

    def test_rejects_file_symlink(self):
        (self.files / "actual.txt").write_bytes(b"synthetic evidence\n")
        (self.files / "sample.txt").symlink_to("actual.txt")
        self.write_manifest([self.entry()])
        self.assertIn("not a regular file", verify_manifest(self.manifest, self.files)[0])

    def test_rejects_directory_symlink(self):
        (self.files / "sample.txt").write_bytes(b"synthetic evidence\n")
        alias = self.base / "alias"
        alias.symlink_to(self.files, target_is_directory=True)
        self.write_manifest([self.entry()])
        with self.assertRaisesRegex(ManifestError, "cannot open target directory"):
            verify_manifest(self.manifest, alias)


if __name__ == "__main__":
    unittest.main()
