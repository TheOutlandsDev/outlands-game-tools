"""Generated source fixtures only; never reads installed games or user data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_STORED, ZipFile

MODULE = Path(__file__).resolve().parents[1] / "source_release.py"
SPEC = importlib.util.spec_from_file_location("source_release", MODULE)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
LICENSE = Path(__file__).resolve().parents[3] / "LICENSE"


class SourceReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        (self.root / "LICENSE").write_bytes(LICENSE.read_bytes())
        (self.root / "hello.py").write_text("print('Original generated example')\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "README.md").write_text("# Generated source\n", encoding="utf-8")
        self.manifest = self.root / builder.MANIFEST
        self.output = self.base / "release.zip"
        self.record()

    def record(self):
        rows = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and path != self.manifest:
                data = path.read_bytes()
                rows.append({"path": path.relative_to(self.root).as_posix(), "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest()})
        self.value = {"schema_version": 1, "license": "MIT", "files": rows}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.value, indent=2) + "\n", encoding="utf-8")

    def build(self, **kwargs):
        return builder.build(self.root, self.output, **kwargs)

    def refusal(self, code=None, **kwargs):
        result = self.build(**kwargs)
        self.assertEqual("FAIL", result["status"], result)
        if code:
            self.assertEqual(code, result["code"], result)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".sha256").exists())
        self.assertNotIn(str(self.root), json.dumps(result))
        return result

    def test_archive_exact_members_bytes_crc_and_checksum(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        result = self.build(prefix="example-v1.0.0")
        self.assertEqual("PASS", result["status"], result)
        self.assertEqual(3, result["source_files"])
        self.assertEqual(4, result["archive_members"])
        with ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(sorted("example-v1.0.0/" + name for name in before), archive.namelist())
            for name, data in before.items():
                self.assertEqual(data, archive.read("example-v1.0.0/" + name))
            for info in archive.infolist():
                self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)
                self.assertEqual(ZIP_STORED, info.compress_type)
                self.assertEqual(0o100644 << 16, info.external_attr)
        digest = hashlib.sha256(self.output.read_bytes()).hexdigest()
        self.assertEqual(digest, result["sha256"])
        self.assertEqual(digest + "  release.zip\n", self.output.with_name("release.zip.sha256").read_text())
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
                                 for p in self.root.rglob("*") if p.is_file()})

    def test_identical_archives_at_two_destinations(self):
        self.assertEqual("PASS", self.build()["status"])
        second = self.base / "another.zip"
        self.assertEqual("PASS", builder.build(self.root, second)["status"])
        self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_manifest_exact_bom_and_whitespace_retained(self):
        data = b"\xef\xbb\xbf" + self.manifest.read_bytes() + b"\n  "
        self.manifest.write_bytes(data)
        self.assertEqual("PASS", self.build()["status"])
        with ZipFile(self.output) as archive:
            self.assertEqual(data, archive.read(builder.MANIFEST))

    def test_unlisted_payload_excluded(self):
        (self.root / "unlisted.md").write_text("Unreviewed text", encoding="utf-8")
        (self.root / "game.dll").write_bytes(b"\0binary")
        self.assertEqual("PASS", self.build()["status"])
        with ZipFile(self.output) as archive:
            self.assertNotIn("unlisted.md", archive.namelist())
            self.assertNotIn("game.dll", archive.namelist())

    def test_missing_source(self):
        (self.root / "hello.py").unlink()
        self.refusal("io_or_archive_failure")

    def test_changed_source(self):
        (self.root / "hello.py").write_text("changed", encoding="utf-8")
        self.refusal("source_manifest_mismatch")

    def test_same_size_changed_source(self):
        source = self.root / "hello.py"
        data = source.read_bytes()
        source.write_bytes(b"X" + data[1:])
        self.refusal("source_manifest_mismatch")

    def test_wrong_mit_declaration(self):
        self.value["license"] = "AGPL-3.0"
        self.write_manifest()
        self.refusal("manifest_schema_invalid")

    def test_missing_root_license(self):
        self.value["files"] = [row for row in self.value["files"] if row["path"] != "LICENSE"]
        self.write_manifest()
        self.refusal("root_license_required")

    def test_license_body_checked_after_hash(self):
        (self.root / "LICENSE").write_text("MIT License\nUnrelated terms\n", encoding="utf-8")
        self.record()
        self.refusal("root_license_not_mit")

    def test_duplicate_json_keys(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1,"license":"MIT","files":[]}', encoding="utf-8")
        self.refusal("manifest_duplicate_key")

    def test_nested_duplicate_json_keys(self):
        self.manifest.write_text('{"schema_version":1,"license":"MIT","files":[{"path":"a.py","path":"b.py"}]}', encoding="utf-8")
        self.refusal("manifest_duplicate_key")

    def test_nonfinite_json_rejected(self):
        self.manifest.write_text('{"schema_version":NaN,"license":"MIT","files":[]}', encoding="utf-8")
        self.refusal("manifest_schema_invalid")

    def test_schema_and_numeric_types(self):
        for field, value in [("schema_version", True), ("schema_version", 2), ("license", None), ("files", {})]:
            with self.subTest(field=field, value=value):
                saved = self.value[field]
                self.value[field] = value
                self.write_manifest()
                self.refusal("manifest_schema_invalid")
                self.value[field] = saved

    def test_record_types_and_extra_keys(self):
        for field, value in [("bytes", True), ("bytes", -1), ("sha256", "A" * 64), ("extra", 1)]:
            with self.subTest(field=field):
                saved = dict(self.value["files"][0])
                self.value["files"][0][field] = value
                self.write_manifest()
                self.refusal("manifest_record_invalid")
                self.value["files"][0] = saved

    def test_manifest_path_traversal_and_devices(self):
        for name in ["../escape.py", "/root.py", "a\\b.py", "a//b.py", "C:/code.py", "a.py:stream",
                     "NUL.py", "CON .py", "NUL .json", "COM1 .py", "aux/readme.md", "CONIN$", "CLOCK$.py", "doc./a.py", "a /b.py", "a\x01.py", "COM1", "a/./b.py"]:
            with self.subTest(name=name):
                self.value["files"][0]["path"] = name
                self.write_manifest()
                self.refusal("manifest_path_invalid")

    def test_no_self_listing(self):
        self.value["files"][0]["path"] = builder.MANIFEST
        self.write_manifest()
        self.refusal("manifest_self_listed")

    def test_duplicate_paths(self):
        self.value["files"].append(dict(self.value["files"][0]))
        self.write_manifest()
        self.refusal("manifest_path_collision")

    def test_case_collision_paths(self):
        duplicate = dict(self.value["files"][0])
        duplicate["path"] = duplicate["path"].lower()
        self.value["files"].append(duplicate)
        self.write_manifest()
        self.refusal("manifest_path_collision")

    def test_case_collision_directories(self):
        row = dict(self.value["files"][0], path="DOCS/extra.py")
        self.value["files"].append(row)
        self.write_manifest()
        self.refusal("manifest_path_collision")

    def test_file_ancestor_collision(self):
        self.value["files"].append(dict(self.value["files"][0], path="hello.py/nested.py"))
        self.write_manifest()
        self.refusal("manifest_path_collision")

    def test_directory_then_file_collision(self):
        self.value["files"].append(dict(self.value["files"][0], path="docs"))
        self.write_manifest()
        self.refusal("manifest_path_collision")

    def test_manifest_depth_limit_before_filesystem_access(self):
        self.value["files"].append(dict(self.value["files"][0], path="a/" * 128 + "file.py"))
        self.write_manifest()
        self.refusal("manifest_path_invalid")

    def test_manifest_maximum_depth_is_accepted_by_parser(self):
        self.value["files"].append(dict(self.value["files"][0], path="a/" * 127 + "file.py"))
        rows = builder.parse_manifest(json.dumps(self.value).encode("utf-8"))
        self.assertEqual(4, len(rows))

    def test_trie_shares_common_directory_prefixes(self):
        for index in range(256):
            self.value["files"].append(dict(self.value["files"][0], path=f"shared/tree/file-{index:03d}.py"))
        rows = builder.parse_manifest(json.dumps(self.value).encode("utf-8"))
        self.assertEqual(259, len(rows))
        self.assertEqual(sorted(row["path"] for row in rows), [row["path"] for row in rows])

    def test_excluded_repository_runtime_directories(self):
        for name in [".git/config.py", ".venv/source.py", "BIN/code.py", "artifacts/log.md"]:
            with self.subTest(name=name):
                self.value["files"][0]["path"] = name
                self.write_manifest()
                self.refusal("source_path_excluded")

    def test_binary_extensions_rejected(self):
        for name in ["game.exe", "audio.ogg", "save.dat", "archive.zip", "diagnostic.log", "requirements.txt",
                     "sample.txt", "tools/another-tool/examples/files/sample.txt",
                     "tools/bounded-evidence-manifest-verifier/examples/files/unreviewed.txt"]:
            with self.subTest(name=name):
                self.value["files"][0]["path"] = name
                self.write_manifest()
                self.refusal("source_type_rejected")

    def test_scoped_requirements_are_supported(self):
        path = self.root / "tools" / "lua-syntax-checker" / "requirements.txt"
        path.parent.mkdir(parents=True)
        path.write_text("lupa==2.6\n", encoding="utf-8")
        self.record()
        self.assertEqual("PASS", self.build()["status"])

    def test_exact_reviewed_synthetic_text_fixture_is_supported(self):
        path = self.root / "tools" / "bounded-evidence-manifest-verifier" / "examples" / "files" / "sample.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"synthetic evidence\n")
        self.record()
        self.assertEqual("PASS", self.build()["status"])

    def test_disguised_binary_nul_or_invalid_utf8(self):
        for data in [b"text\0binary", b"invalid\xff"]:
            with self.subTest(data=data):
                (self.root / "hello.py").write_bytes(data)
                self.record()
                self.refusal("source_text_required")

    def test_manifest_byte_limit(self):
        with patch.object(builder, "MAX_MANIFEST_BYTES", 16):
            self.refusal("manifest_limit_exceeded")

    def test_file_count_limit(self):
        with patch.object(builder, "MAX_FILES", 2):
            self.refusal("file_count_limit")

    def test_file_byte_limit(self):
        with patch.object(builder, "MAX_FILE_BYTES", 16):
            self.refusal("manifest_record_invalid")

    def test_total_byte_limit(self):
        with patch.object(builder, "MAX_TOTAL_BYTES", 16):
            self.refusal("total_byte_limit")

    def test_prefix_restrictions(self):
        for prefix in ["../escape", "a/b", "NUL", "bad.", "", "a" * 81]:
            with self.subTest(prefix=prefix):
                self.refusal("prefix_invalid", prefix=prefix)

    def test_canonical_manifest_only(self):
        alternate = self.base / "alternate.json"
        alternate.write_bytes(self.manifest.read_bytes())
        self.refusal("canonical_manifest_required", manifest=alternate)

    def test_existing_zip_not_overwritten(self):
        self.output.write_bytes(b"keep")
        result = self.build()
        self.assertEqual("output_exists", result["code"])
        self.assertEqual(b"keep", self.output.read_bytes())
        self.assertFalse(self.base.joinpath("release.zip.sha256").exists())

    def test_existing_checksum_prevents_any_zip(self):
        checksum = self.base / "release.zip.sha256"
        checksum.write_bytes(b"keep")
        result = self.build()
        self.assertEqual("output_exists", result["code"])
        self.assertFalse(self.output.exists())
        self.assertEqual(b"keep", checksum.read_bytes())

    def test_output_inside_source(self):
        result = builder.build(self.root, self.root / "release.zip")
        self.assertEqual("output_inside_source", result["code"])
        self.assertFalse((self.root / "release.zip").exists())

    def test_missing_parent_is_not_created(self):
        result = builder.build(self.root, self.base / "absent" / "release.zip")
        self.assertEqual("FAIL", result["status"])
        self.assertFalse((self.base / "absent").exists())

    def test_drive_relative_and_network_paths_rejected(self):
        for name in ["F:folder", "F:", "//server/share", "\\\\server\\share", "\\\\?\\C:\\folder"]:
            with self.subTest(name=name):
                result = builder.build(name, self.output)
                self.assertEqual("input_path_invalid", result["code"])

    def test_cleanup_never_removes_a_different_file(self):
        self.output.write_bytes(b"keep")
        other = self.base / "other.py"
        other.write_bytes(b"different object")
        self.assertFalse(builder.remove_owned(self.output, other.stat()))
        self.assertEqual(b"keep", self.output.read_bytes())

    def test_failed_cleanup_is_explicitly_reported(self):
        with patch.object(builder, "verify_archive", side_effect=builder.BuildError("archive_bytes_mismatch")):
            with patch.object(builder, "remove_owned", return_value=False):
                result = self.build()
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(result["partial_outputs_possible"])
        self.assertEqual(2, result["created_outputs"])
        self.assertEqual(0, result["removed_outputs"])

    def test_corrupt_archive_verification_removes_outputs(self):
        with patch.object(builder, "verify_archive", side_effect=builder.BadZipFile("private failure")):
            self.refusal("io_or_archive_failure")

    def test_source_change_during_archive_verification_is_detected(self):
        real = builder.verify_archive
        def change(stream, expected):
            real(stream, expected)
            (self.root / "hello.py").write_text("changed during verification", encoding="utf-8")
        with patch.object(builder, "verify_archive", side_effect=change):
            self.refusal("source_manifest_mismatch")

    def test_regular_file_required_before_opening(self):
        path = self.root / "hello.py"
        path.unlink()
        path.mkdir()
        self.refusal("regular_file_required")

    def test_device_guards_are_pure_validation(self):
        for value in ["CON .py", "NUL .json", "COM1 .py", "LPT9 .md", "CONIN$", "CONOUT$.py"]:
            self.assertFalse(builder.portable_component(value), value)

    def test_interrupted_copy_removes_only_owned_outputs(self):
        real = builder.source_bytes
        def interrupted(root, row, destination=None):
            if destination is not None:
                destination.write(b"partial")
                raise OSError("private raw exception deliberately omitted")
            return real(root, row, destination)
        with patch.object(builder, "source_bytes", side_effect=interrupted):
            result = self.refusal("io_or_archive_failure")
        self.assertEqual(2, result["created_outputs"])
        self.assertEqual(2, result["removed_outputs"])
        self.assertFalse(result["partial_outputs_possible"])
        self.assertNotIn("private", json.dumps(result))

    def test_manifest_changes_while_writing_are_detected(self):
        real = builder.source_bytes
        changed = False
        def change(root, row, destination=None):
            nonlocal changed
            result = real(root, row, destination)
            if destination is not None and not changed:
                changed = True
                self.manifest.write_bytes(self.manifest.read_bytes() + b" ")
            return result
        with patch.object(builder, "source_bytes", side_effect=change):
            self.refusal("source_changed")

    def test_source_changes_after_copy_are_detected(self):
        real = builder.source_bytes
        changed = False
        def change(root, row, destination=None):
            nonlocal changed
            result = real(root, row, destination)
            if destination is not None and row["path"] == "hello.py" and not changed:
                changed = True
                (self.root / "hello.py").write_text("changed", encoding="utf-8")
            return result
        with patch.object(builder, "source_bytes", side_effect=change):
            self.refusal("source_manifest_mismatch")

    def symlink(self, target, link, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("Native symbolic-link creation unavailable")

    def test_file_link_rejected(self):
        target = self.base / "linked-source.py"
        target.write_bytes((self.root / "hello.py").read_bytes())
        (self.root / "hello.py").unlink()
        self.symlink(target, self.root / "hello.py")
        self.refusal("linked_path_rejected")

    def test_linked_source_ancestor_rejected(self):
        link = self.base / "linked-root"
        self.symlink(self.root, link, True)
        result = builder.build(link, self.output)
        self.assertEqual("linked_path_rejected", result["code"])

    def test_linked_output_parent_rejected(self):
        target = self.base / "output-parent"
        target.mkdir()
        link = self.base / "output-link"
        self.symlink(target, link, True)
        result = builder.build(self.root, link / "release.zip")
        self.assertEqual("linked_path_rejected", result["code"])
        self.assertFalse((target / "release.zip").exists())

    def test_manifest_link_rejected(self):
        target = self.base / builder.MANIFEST
        target.write_bytes(self.manifest.read_bytes())
        self.manifest.unlink()
        self.symlink(target, self.manifest)
        self.refusal("linked_path_rejected")

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_ancestor_rejected_without_following_cleanup(self):
        link = self.base / "junction"
        environment = dict(os.environ, BUILDER_TEST_LINK=str(link), BUILDER_TEST_TARGET=str(self.root))
        script = ("New-Item -ItemType Junction -Path $env:BUILDER_TEST_LINK "
                  "-Target $env:BUILDER_TEST_TARGET -ErrorAction Stop | Out-Null")
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                   env=environment, capture_output=True, timeout=20)
        if completed.returncode:
            self.skipTest("Native junction creation unavailable")
        try:
            result = builder.build(link, self.output)
            self.assertEqual("linked_path_rejected", result["code"])
        finally:
            # Remove only the junction itself, never recurse through its target.
            if link.is_junction():
                self.assertEqual(self.base.resolve(strict=True), link.parent.resolve(strict=True))
                self.assertTrue(self.root.resolve(strict=True).is_relative_to(self.base.resolve(strict=True)))
                self.assertEqual(link.resolve(strict=True), self.root.resolve(strict=True))
                link.rmdir()
        self.assertTrue((self.root / "LICENSE").is_file())

    def test_cli_json_success_and_no_private_paths(self):
        completed = subprocess.run([sys.executable, "-B", str(MODULE), "--source-root", str(self.root),
                                    "--output", str(self.output)], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("PASS", result["status"])
        self.assertNotIn(str(self.root), completed.stdout)
        self.assertEqual("", completed.stderr)

    def test_cli_bad_arguments_do_not_echo_user_values(self):
        completed = subprocess.run([sys.executable, "-B", str(MODULE), "--private-secret-value"],
                                   capture_output=True, text=True)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("arguments_invalid", json.loads(completed.stdout)["code"])
        self.assertNotIn("private-secret-value", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
