"""Generated-fixture CLI and transaction tests; never reads an installed game."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "profile_builder.py"
ALLOW = ("modlist.txt", "archives.txt", "initweaks.ini", "lockedorder.txt", "settings.ini")


class ProfileBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mo2-profile-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.destination = self.root / "comparison"
        self.modlist = self.source / "modlist.txt"
        self.modlist.write_bytes(b"# Original MO2 order\r\n+High Priority\r\n+Example Mod\r\n-Disabled Mod\r\n")
        self.links = []
        self.addCleanup(self.clean_links)

    def clean_links(self):
        for path in reversed(self.links):
            if path.is_symlink():
                path.unlink()
            elif path.exists():
                # Native junction removal must never recurse into its target.
                path.rmdir()

    def command(self, *extra, source=None, destination=None, disable=None):
        args = ["--source-profile", str(source or self.source), "--destination", str(destination or self.destination)]
        for name in disable if disable is not None else ["Example Mod"]:
            args += ["--disable", name]
        return args + list(extra)

    def run_cli(self, *extra, source=None, destination=None, disable=None, expected=0):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT)] + self.command(
            *extra, source=source, destination=destination, disable=disable), capture_output=True)
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        self.assertEqual(result.stderr, b"")
        report = json.loads(result.stdout) if result.stdout else None
        return report

    def reject(self, error, *extra, **kwargs):
        before = self.modlist.read_bytes()
        report = self.run_cli(*extra, expected=1, **kwargs)
        self.assertEqual(report["status"], "ERROR")
        self.assertFalse(report["complete"])
        self.assertEqual(report["error"], error)
        self.assertEqual(self.modlist.read_bytes(), before)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])
        return report

    def make_link(self, link, target, *, directory=True):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError:
            if os.name != "nt" or not directory:
                self.skipTest("Native symlink privilege unavailable")
            quoted_link = str(link).replace("'", "''")
            quoted_target = str(target).replace("'", "''")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path '" + quoted_link + "' -Target '" + quoted_target + "' | Out-Null"], capture_output=True)
            if result.returncode:
                self.skipTest("Native junction creation unavailable")
        self.links.append(link)

    def fault_run(self, patch, expected=1):
        wrapper = """import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('builder_under_test',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
""" + patch + "\nraise SystemExit(module.main(sys.argv[2:]))\n"
        result = subprocess.run([sys.executable, "-B", "-c", wrapper, str(SCRIPT)] + self.command("--apply", "--confirm-closed"), capture_output=True)
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout)

    def test_preview_has_no_filesystem_changes(self):
        before = self.modlist.read_bytes()
        report = self.run_cli()
        self.assertEqual(report["status"], "PREVIEW")
        self.assertTrue(report["source_verified_unchanged"])
        self.assertFalse(report["destination_verified"])
        self.assertEqual(report["changes"]["enabled_after"], 1)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.modlist.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["source"])

    def test_apply_exact_bytes_and_source_unchanged(self):
        before = self.modlist.read_bytes()
        report = self.run_cli("--apply", "--confirm-closed")
        expected = before.replace(b"+Example Mod", b"-Example Mod")
        self.assertEqual(self.modlist.read_bytes(), before)
        self.assertEqual((self.destination / "modlist.txt").read_bytes(), expected)
        self.assertEqual(report["status"], "APPLIED")
        self.assertTrue(report["destination_verified"])
        self.assertEqual(report["files"][0]["destination_sha256"], hashlib.sha256(expected).hexdigest())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])

    def test_optional_allowlist_only_copied_byte_for_byte(self):
        for name in ALLOW[1:]:
            (self.source / name).write_bytes(b"private-value=do-not-report\x00\xff\r\n")
        (self.source / "plugins.txt").write_text("not copied", encoding="utf-8")
        (self.source / "loadorder.txt").write_text("not copied", encoding="utf-8")
        (self.source / "saves").mkdir()
        (self.source / "saves" / "save.dat").write_bytes(b"private save")
        report = self.run_cli("--apply", "--confirm-closed")
        self.assertEqual(set(p.name for p in self.destination.iterdir()), set(ALLOW))
        for name in ALLOW[1:]:
            self.assertEqual((self.destination / name).read_bytes(), (self.source / name).read_bytes())
        encoded = json.dumps(report)
        self.assertNotIn("private-value", encoded)
        self.assertNotIn(str(self.root), encoded)

    def test_bom_mixed_newlines_no_final_newline_preserved(self):
        before = b"\xef\xbb\xbf# Note\r\n+High Priority\n+Example Mod\r-Disabled Mod"
        self.modlist.write_bytes(before)
        self.run_cli("--apply", "--confirm-closed")
        self.assertEqual((self.destination / "modlist.txt").read_bytes(), before.replace(b"+Example Mod", b"-Example Mod"))

    def test_multiple_requests_only_change_markers(self):
        before = self.modlist.read_bytes()
        self.run_cli("--apply", "--confirm-closed", disable=["Example Mod", "High Priority"])
        self.assertEqual((self.destination / "modlist.txt").read_bytes(), before.replace(b"+Example Mod", b"-Example Mod").replace(b"+High Priority", b"-High Priority"))

    def test_apply_requires_closed_attestation(self):
        self.reject("closed_attestation_required", "--apply")

    def test_closed_flag_without_apply_rejected(self):
        self.reject("closed_attestation_requires_apply", "--confirm-closed")

    def test_missing_mod_rejected(self):
        self.reject("requested_mod_missing", disable=["Foreign Mod"])

    def test_disabled_mod_rejected(self):
        self.reject("requested_mod_already_disabled", disable=["Disabled Mod"])

    def test_case_mismatch_rejected(self):
        self.reject("requested_mod_case_mismatch", disable=["example mod"])

    def test_duplicate_requests_rejected(self):
        self.reject("duplicate_disable_request", disable=["Example Mod", "EXAMPLE MOD"])

    def test_unsafe_requests_rejected(self):
        for name in ("../Escape", "CON", "name:ads", "trailing.", " padded ", "Folder\\Mod", "Example_separator"):
            with self.subTest(name=name):
                self.reject("unsafe_mod_request", disable=[name])

    def test_foreign_modlist_entry_rejected(self):
        self.modlist.write_bytes(b"+Example Mod\n*Foreign entry\n")
        self.reject("unsupported_modlist_entry")

    def test_duplicate_modlist_entry_rejected(self):
        self.modlist.write_bytes(b"+Example Mod\n-EXAMPLE MOD\n")
        self.reject("duplicate_modlist_entry")

    def test_invalid_utf8_rejected(self):
        self.modlist.write_bytes(b"+Example Mod\n\xff")
        self.reject("unsupported_modlist_encoding")

    def test_binary_modlist_rejected(self):
        self.modlist.write_bytes(b"+Example Mod\x00\n")
        self.reject("invalid_modlist_text")

    def test_missing_modlist_rejected(self):
        self.modlist.unlink()
        report = self.run_cli(expected=1)
        self.assertEqual(report["error"], "missing_modlist")
        self.assertFalse(self.destination.exists())

    def test_case_variant_profile_filename_rejected(self):
        self.modlist.rename(self.source / "Modlist.txt")
        report = self.run_cli(expected=1)
        self.assertEqual(report["error"], "ambiguous_profile_filename")

    def test_optional_directory_rejected(self):
        (self.source / "settings.ini").mkdir()
        self.reject("nonregular_profile_file")

    def test_oversize_optional_file_rejected(self):
        with (self.source / "settings.ini").open("wb") as stream:
            stream.truncate(2 * 1024 * 1024 + 1)
        self.reject("profile_file_size_limit")

    def test_source_destination_overlap_rejected(self):
        self.reject("source_destination_overlap", destination=self.source / "nested")

    def test_existing_destination_untouched(self):
        self.destination.mkdir()
        marker = self.destination / "keep.txt"
        marker.write_bytes(b"keep")
        report = self.run_cli("--apply", "--confirm-closed", expected=1)
        self.assertEqual(report["error"], "destination_exists")
        self.assertEqual(marker.read_bytes(), b"keep")

    def test_case_variant_destination_rejected(self):
        existing = self.root / "COMPARISON"
        existing.mkdir()
        report = self.run_cli(expected=1)
        self.assertEqual(report["error"], "destination_exists")

    def test_unc_and_device_and_ads_paths_rejected(self):
        for value in ("\\\\server\\share\\profile", "//server/share/profile", str(self.root / "NUL"), str(self.root / "report:ads")):
            with self.subTest(value=value):
                report = self.run_cli(source=value, expected=1)
                self.assertIn(report["error"], ("unsupported_path", "unsafe_path_component"))

    def test_drive_relative_paths_rejected_without_cwd_resolution(self):
        for value in ("F:folder", "F:", "C:relative-profile"):
            with self.subTest(value=value):
                self.reject("unsupported_path", source=value)

    def test_invalid_cli_does_not_echo_private_argument(self):
        secret = "private-path-or-token-should-not-be-reported"
        result = subprocess.run([sys.executable, "-B", str(SCRIPT)] + self.command("--unknown-" + secret, secret), capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(secret.encode(), result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["error"], "invalid_arguments")
        self.assertFalse(report["complete"])
        self.assertFalse(self.destination.exists())

    def test_new_report_created_outside_roots(self):
        output = self.root / "report.json"
        report = self.run_cli("--output", str(output))
        self.assertIsNone(report)
        saved = json.loads(output.read_bytes())
        self.assertEqual(saved["status"], "PREVIEW")
        self.assertFalse(self.destination.exists())

    def test_existing_report_prevents_apply(self):
        output = self.root / "report.json"
        output.write_bytes(b"keep")
        self.reject("destination_exists", "--output", str(output), "--apply", "--confirm-closed")
        self.assertEqual(output.read_bytes(), b"keep")

    def test_report_inside_source_prevents_apply(self):
        self.reject("output_overlaps_inputs", "--output", str(self.source / "report.json"), "--apply", "--confirm-closed")

    def test_report_inside_destination_prevents_apply(self):
        self.reject("output_overlaps_inputs", "--output", str(self.destination / "report.json"), "--apply", "--confirm-closed")

    def test_missing_report_parent_prevents_apply(self):
        self.reject("missing_or_unreadable_path", "--output", str(self.root / "missing" / "report.json"), "--apply", "--confirm-closed")

    def test_linked_source_directory_rejected(self):
        link = self.root / "linked-source"
        self.make_link(link, self.source)
        self.reject("linked_path", source=link)

    def test_linked_optional_file_rejected(self):
        target = self.root / "outside.ini"
        target.write_bytes(b"private")
        self.make_link(self.source / "settings.ini", target, directory=False)
        self.reject("linked_path")

    def test_linked_destination_parent_rejected(self):
        real = self.root / "real-parent"
        real.mkdir()
        linked = self.root / "linked-parent"
        self.make_link(linked, real)
        self.reject("linked_path", destination=linked / "comparison")

    def test_linked_report_parent_prevents_apply(self):
        real = self.root / "real-reports"
        real.mkdir()
        linked = self.root / "linked-reports"
        self.make_link(linked, real)
        self.reject("linked_path", "--output", str(linked / "report.json"), "--apply", "--confirm-closed")

    def test_partial_destination_failure_rolls_back_only_new_files(self):
        patch = """real=module.create_file
def injected(path,data):
    if path.parent.name == 'comparison' and path.name == 'settings.ini':
        raise OSError('injected disk error with private path')
    return real(path,data)
module.create_file=injected
"""
        (self.source / "settings.ini").write_bytes(b"setting=value\n")
        before = self.modlist.read_bytes()
        report = self.fault_run(patch)
        self.assertEqual(report["error"], "apply_failed_rolled_back")
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])
        self.assertEqual(self.modlist.read_bytes(), before)
        self.assertNotIn("private path", json.dumps(report))

    def test_source_change_during_staging_aborts_before_destination(self):
        patch = """real=module.verify_source
calls=0
def injected(source,originals,state):
    global calls
    calls+=1
    if calls == 2:
        (source/'settings.ini').write_bytes(b'external change')
    return real(source,originals,state)
module.verify_source=injected
"""
        (self.source / "settings.ini").write_bytes(b"initial")
        report = self.fault_run(patch)
        self.assertEqual(report["error"], "apply_failed_rolled_back")
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])
        self.assertEqual((self.source / "settings.ini").read_bytes(), b"external change")

    def test_foreign_file_appearing_in_new_destination_is_preserved(self):
        patch = """real=module.create_file
def injected(path,data):
    if path.parent.name == 'comparison':
        (path.parent/'foreign.txt').write_bytes(b'preserve external file')
        raise OSError('injected interruption')
    return real(path,data)
module.create_file=injected
"""
        report = self.fault_run(patch)
        self.assertEqual(report["error"], "rollback_incomplete")
        self.assertEqual((self.destination / "foreign.txt").read_bytes(), b"preserve external file")
        self.assertFalse((self.destination / "modlist.txt").exists())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])

    def test_unexpected_file_detected_during_destination_verification(self):
        patch = """real=module.create_file
def injected(path,data):
    result=real(path,data)
    if path.parent.name == 'comparison':
        (path.parent/'foreign.txt').write_bytes(b'preserve external file')
    return result
module.create_file=injected
"""
        report = self.fault_run(patch)
        self.assertEqual(report["error"], "rollback_incomplete")
        self.assertEqual((self.destination / "foreign.txt").read_bytes(), b"preserve external file")
        self.assertFalse((self.destination / "modlist.txt").exists())
        self.assertEqual(list(self.root.glob(".mo2-profile-stage-*")), [])

    def test_apply_writes_new_report_with_verification(self):
        output = self.root / "applied.json"
        self.assertIsNone(self.run_cli("--apply", "--confirm-closed", "--output", str(output)))
        report = json.loads(output.read_bytes())
        self.assertEqual(report["status"], "APPLIED")
        self.assertTrue(report["destination_verified"])
        self.assertTrue(self.destination.is_dir())

    def test_generated_example_runs_and_refuses_existing_directory(self):
        generator = SCRIPT.parent / "examples" / "create_example.py"
        example = self.root / "generated"
        command = [sys.executable, "-B", str(generator), str(example)]
        first = subprocess.run(command, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = (example / "Original Profile" / "modlist.txt").read_bytes()
        report = self.run_cli(source=example / "Original Profile", destination=example / "Comparison Profile", disable=["Example Content Mod"])
        self.assertEqual(report["changes"]["enabled_before"], 3)
        self.assertEqual(report["changes"]["enabled_after"], 2)
        second = subprocess.run(command, capture_output=True)
        self.assertEqual(second.returncode, 1)
        self.assertEqual((example / "Original Profile" / "modlist.txt").read_bytes(), original)

    def test_help_and_version(self):
        for option in ("--help", "--version"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), option], capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout)
            self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
