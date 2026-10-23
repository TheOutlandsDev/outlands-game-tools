# SPDX-License-Identifier: MIT
"""Synthetic regressions for deliberate unsupported-platform behavior."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_manifest as verifier


class PlatformTests(unittest.TestCase):
    def test_unsupported_api_refuses_before_opening_inputs(self):
        with mock.patch.object(verifier, "_platform_supported", return_value=False):
            with mock.patch.object(verifier.os, "open") as opened:
                for operation, arguments in (
                    (verifier.load_manifest, (Path("fictional-manifest.json"),)),
                    (verifier.verify_manifest, (Path("fictional-manifest.json"), Path("fictional-files"))),
                ):
                    with self.subTest(operation=operation.__name__):
                        with self.assertRaisesRegex(verifier.ManifestError, "Windows is unsupported"):
                            operation(*arguments)
                opened.assert_not_called()

    def test_unsupported_cli_returns_two_without_traceback(self):
        program = (
            "import sys; import verify_manifest as v; "
            "v._platform_supported = lambda: False; "
            "sys.argv = ['verify_manifest.py', 'fictional-manifest.json', 'fictional-files']; "
            "raise SystemExit(v.main())"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", program],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "INVALID: requires POSIX no-follow, descriptor-relative file APIs; Windows is unsupported\n",
        )

    @unittest.skipUnless(os.name == "nt", "Windows-only rejection check")
    def test_native_windows_cli_is_explicitly_unsupported(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", str(root / "verify_manifest.py"),
             str(root / "examples" / "manifest.json"), str(root / "examples" / "files")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Windows is unsupported", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
