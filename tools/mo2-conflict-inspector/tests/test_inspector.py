"""Black-box CLI checks using synthetic MO2 folders only.

These checks launch the public command with the current Python interpreter.
They never inspect, modify, or launch an installed game or Mod Organizer.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "mo2_conflicts.py"


class InspectorCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mo2-inspector-tests-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.mods = self.base / "mods with spaces"
        self.mods.mkdir()
        self.modlist = self.base / "profile with spaces" / "modlist.txt"
        self.modlist.parent.mkdir()
        self.overwrite = self.base / "overwrite"
        self.overwrite.mkdir()
        self.report_number = 0
        self.set_modlist("+High", "+Low")
        (self.mods / "High").mkdir()
        (self.mods / "Low").mkdir()

    def set_modlist(self, *lines):
        self.modlist.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def file(self, provider, relative, contents):
        folder = self.overwrite if provider == "overwrite" else self.mods / provider
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            target.write_bytes(contents)
        else:
            target.write_text(contents, encoding="utf-8")
        return target

    def command(self, *extra, output=None, mods=None):
        self.report_number += 1
        destination = output or self.base / f"report-{self.report_number}.json"
        process = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--mods-dir", str(mods or self.mods),
             "--modlist", str(self.modlist), "--output", str(destination), *extra],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        return process, destination

    def inspect(self, *extra, status=0):
        process, destination = self.command(*extra)
        self.assertEqual(process.returncode, status, process.stdout + process.stderr)
        self.assertTrue(destination.is_file(), "The CLI did not create its requested report")
        raw = destination.read_text(encoding="utf-8")
        report = json.loads(raw)
        self.assertEqual(report["schema_version"], 1)
        # Check decoded strings too: JSON escapes Windows backslashes, which can
        # otherwise make an absolute-path leakage assertion accidentally pass.
        public_text = "\n".join(self.string_values(report)) + process.stdout + process.stderr
        self.assertNotIn(str(self.base), public_text)
        self.assertNotIn(self.base.as_posix(), public_text.replace("\\", "/"))
        return report, process

    @classmethod
    def string_values(cls, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from cls.string_values(key)
                yield from cls.string_values(item)
        elif isinstance(value, list):
            for item in value:
                yield from cls.string_values(item)

    @staticmethod
    def input_snapshot(*roots):
        result = {}
        for number, root in enumerate(roots):
            entries = [root] if root.is_file() else [root, *root.rglob("*")]
            for entry in entries:
                relative = "." if entry == root else entry.relative_to(root).as_posix()
                key = (number, relative)
                metadata = entry.stat()
                result[key] = (metadata.st_mtime_ns, metadata.st_size,
                               hashlib.sha256(entry.read_bytes()).hexdigest()
                               if entry.is_file() else None)
        return result

    def test_clean_profile_and_public_help(self):
        report, _ = self.inspect("--fail-on-conflicts")
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["findings"], 0)
        help_result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--help"],
                                     capture_output=True, text=True, timeout=30)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("--mods-dir", help_result.stdout)
        self.assertIn("--fail-on-conflicts", help_result.stdout)

    def test_stdout_json_and_version(self):
        self.set_modlist("+A mod with spaces")
        self.file("A mod with spaces", "gamedata/read me.bin", b"synthetic")
        process = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--mods-dir", str(self.mods),
             "--modlist", str(self.modlist)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["effective_files"], 1)
        self.assertEqual(report["providers_priority_highest_first"][0]["name"], "A mod with spaces")
        self.assertNotIn(str(self.base), process.stdout + process.stderr)
        version = subprocess.run([sys.executable, "-B", str(SCRIPT), "--version"],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(version.returncode, 0)
        self.assertIn(report["tool"]["version"], version.stdout)

    def test_repeated_inspection_is_deterministic(self):
        self.file("High", "z.bin", b"last")
        self.file("Low", "z.bin", b"hidden")
        self.file("High", "a.script", "function repeated.call() end")
        self.file("Low", "b.script", "function repeated.call() end")
        first, _ = self.inspect()
        second, _ = self.inspect()
        self.assertEqual(first, second)

    def test_mo2_highest_first_priority_for_identical_and_different_files(self):
        self.file("High", "gamedata/same.bin", b"same bytes")
        self.file("Low", "gamedata/same.bin", b"same bytes")
        self.file("High", "gamedata/different.bin", b"winning bytes")
        self.file("Low", "gamedata/different.bin", b"losing bytes")
        report, _ = self.inspect()
        conflicts = {item["path"]: item for item in report["file_conflicts"]}
        self.assertEqual(set(conflicts), {"gamedata/same.bin", "gamedata/different.bin"})
        for item in conflicts.values():
            self.assertEqual(item["winner"], "High")
            self.assertEqual(item["providers_highest_first"], ["High", "Low"])
        self.assertEqual(report["summary"]["effective_files"], 2)
        self.assertEqual(report["summary"]["loose_files"], 4)

    def test_overwrite_wins_over_active_mods(self):
        for provider in ("High", "Low", "overwrite"):
            self.file(provider, "gamedata/settings.bin", provider)
        report, _ = self.inspect("--overwrite-dir", str(self.overwrite))
        conflict = report["file_conflicts"][0]
        highest = report["providers_priority_highest_first"][0]
        self.assertEqual(highest["kind"], "overwrite")
        self.assertEqual(conflict["winner"], highest["name"])
        self.assertEqual(conflict["providers_highest_first"], [highest["name"], "High", "Low"])

    def test_overlapping_mods_and_overwrite_roots_are_rejected(self):
        for overwrite in (self.mods / "High", self.base):
            with self.subTest(overwrite=overwrite.name):
                process = subprocess.run(
                    [sys.executable, "-B", str(SCRIPT), "--mods-dir", str(self.mods),
                     "--modlist", str(self.modlist), "--overwrite-dir", str(overwrite)],
                    capture_output=True, text=True, encoding="utf-8", timeout=30,
                )
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                report = json.loads(process.stdout)
                self.assertFalse(report["summary"]["complete"])
                self.assertTrue(report["errors"])
                self.assertNotIn(str(self.base), process.stdout + process.stderr)

    def test_disabled_entries_and_separators_do_not_supply_files(self):
        self.set_modlist("# synthetic MO2 profile", "+High", "-Disabled_missing",
                         "+Tools_separator", "+Low")
        self.file("Tools_separator", "gamedata/ignored.script", "function ignored.call() end")
        report, _ = self.inspect()
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["enabled_mods"], 2)
        self.assertEqual(report["summary"]["loose_files"], 0)
        self.assertEqual([p["name"] for p in report["providers_priority_highest_first"]],
                         ["High", "Low"])

    def test_foreign_and_bare_rows_make_report_incomplete(self):
        for row in ("*Foreign managed elsewhere", "Bare unsupported row"):
            with self.subTest(row=row):
                self.set_modlist("+High", row, "+Low")
                report, _ = self.inspect(status=1)
                self.assertFalse(report["summary"]["complete"])
                self.assertTrue(report["warnings"])
                self.assertEqual(report["summary"]["enabled_mods"], 2)

    def test_mo2_metadata_and_hidden_files_or_folders_are_excluded(self):
        for provider in ("High", "Low"):
            self.file(provider, "meta.ini", "private MO2 metadata")
            self.file(provider, "gamedata/hidden.script.mohidden", "function hidden.call() end")
            self.file(provider, "gamedata/disabled.mohidden/deep.script", "function hidden.call() end")
            self.file(provider, "gamedata/kept.bin", b"kept")
        report, _ = self.inspect()
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["loose_files"], 2)
        self.assertEqual([item["path"] for item in report["file_conflicts"]], ["gamedata/kept.bin"])
        self.assertEqual(report["analysis"]["lua_function_repeats"], [])

    def test_windows_style_case_insensitive_relative_paths(self):
        self.file("High", "GameData/Scripts/Controls.SCRIPT", "return true")
        self.file("Low", "gamedata/scripts/controls.script", "return false")
        report, _ = self.inspect()
        self.assertEqual(len(report["file_conflicts"]), 1)
        self.assertEqual(report["file_conflicts"][0]["path"], "gamedata/scripts/controls.script")
        self.assertEqual(report["file_conflicts"][0]["winner"], "High")

    def test_ambiguous_case_within_one_mod_is_incomplete(self):
        first = self.file("High", "gamedata/Case.script", "function one.call() end")
        second = self.mods / "High" / "gamedata" / "case.script"
        second.write_text("function two.call() end", encoding="utf-8")
        if first.samefile(second):
            self.skipTest("The temporary filesystem does not allow ambiguous filename casing")
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(any(item["code"] == "ambiguous_case_path" for item in report["warnings"]))
        self.assertEqual(report["summary"]["effective_files"], 0)

    def test_missing_enabled_mod_is_incomplete(self):
        self.set_modlist("+Missing", "+High")
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(report["warnings"] or report["errors"])

    def test_unsafe_active_names_are_rejected_without_reading_outside(self):
        self.file("High", "safe.bin", b"safe")
        outside = self.base / "Outside"
        outside.mkdir()
        (outside / "private.script").write_text("function private.external() end", encoding="utf-8")
        for name in ("../Outside", "..\\Outside", "High/nested", str(outside)):
            with self.subTest(name=name):
                self.set_modlist("+" + name)
                report, _ = self.inspect(status=1)
                self.assertFalse(report["summary"]["complete"])
                self.assertTrue(report["errors"])
                self.assertEqual(report["summary"]["loose_files"], 0)

    def test_case_insensitive_duplicate_active_names_are_invalid(self):
        self.set_modlist("+High", "+high")
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(any(item["code"] == "duplicate_mod_name" for item in report["errors"]))

    def test_only_winning_files_supply_lua_declarations(self):
        self.file("High", "gamedata/scripts/shared.script", "function top.only() end")
        self.file("Low", "gamedata/scripts/shared.script", "function hidden.repeat() end")
        self.file("High", "gamedata/scripts/other.script", "function hidden.repeat() end")
        report, _ = self.inspect()
        self.assertEqual(report["analysis"]["lua_function_repeats"], [])
        self.assertEqual(report["summary"]["file_conflicts"], 1)

    def test_qualified_lua_repeats_ignore_comments_strings_and_plain_helpers(self):
        source = (
            "function controls.tick() return true end\n"
            "-- function fake.comment() end\n"
            "--[[ function fake.block() end ]]\n"
            "--[=[ function fake.longcomment() end ]=]\n"
            "local text = 'function fake.quoted() end'\n"
            'local long = [=[function fake.longstring() end]=]\n'
            "local function helper() return false end\n"
            "function init() return true end\n"
        )
        self.file("High", "gamedata/scripts/first.script", source)
        self.file("Low", "gamedata/scripts/second.script", source)
        report, _ = self.inspect()
        repeats = report["analysis"]["lua_function_repeats"]
        self.assertEqual([item["symbol"] for item in repeats], ["controls.tick"])
        self.assertEqual({ref["line"] for ref in repeats[0]["declarations"]}, {1})
        self.assertEqual({ref["provider"] for ref in repeats[0]["declarations"]}, {"High", "Low"})

    def test_ltx_duplicate_keys_stay_within_file_and_section(self):
        self.file("High", "gamedata/configs/repeated.ltx",
                  "[scope]\nsetting = first-private-value\n;setting = commented\n"
                  "setting = second-private-value\n[other]\nsetting = separate\n")
        self.file("Low", "gamedata/configs/separate.ltx", "[scope]\nsetting = other-file\n")
        report, _ = self.inspect()
        duplicates = report["analysis"]["ltx_duplicate_keys"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual((duplicates[0]["section"], duplicates[0]["key"]), ("scope", "setting"))
        self.assertEqual([ref["line"] for ref in duplicates[0]["declarations"]], [2, 4])
        self.assertEqual({ref["path"] for ref in duplicates[0]["declarations"]},
                         {"gamedata/configs/repeated.ltx"})

    def test_unlocalizer_repeats_across_effective_files(self):
        body = "[localize]\ntarget\n; commented_target\n"
        self.file("High", "gamedata/configs/unlocalizers/one.ltx", body)
        self.file("Low", "gamedata/configs/unlocalizers/two.ltx", body)
        report, _ = self.inspect()
        duplicates = report["analysis"]["unlocalizer_duplicates"]
        self.assertEqual([item["symbol"] for item in duplicates], ["localize.target"])
        self.assertEqual({ref["line"] for ref in duplicates[0]["declarations"]}, {2})

    def test_report_contains_declarations_but_no_source_values_or_absolute_paths(self):
        private = "SYNTHETIC_PRIVATE_VALUE_7a9f42"
        lua = f'function controls.tick() local value = "{private}:{self.base}" end\n'
        self.file("High", "gamedata/scripts/a.script", lua)
        self.file("Low", "gamedata/scripts/b.script", lua)
        self.file("High", "gamedata/configs/repeated.ltx",
                  f"[scope]\nsetting = {private}\nsetting = {self.base}\n")
        report, process = self.inspect()
        combined = json.dumps(report) + process.stdout + process.stderr
        self.assertNotIn(private, combined)
        self.assertNotIn("local value", combined)
        self.assertNotIn("setting =", combined)
        self.assertEqual(report["summary"]["lua_function_repeats"], 1)
        self.assertEqual(report["summary"]["ltx_duplicate_keys"], 1)

    def test_inspection_does_not_mutate_inputs(self):
        self.file("High", "gamedata/scripts/first.script", "function shared.call() end")
        self.file("Low", "gamedata/scripts/second.script", "function shared.call() end")
        self.file("overwrite", "notes.bin", b"synthetic overwrite content")
        roots = (self.mods, self.modlist, self.overwrite)
        before = self.input_snapshot(*roots)
        self.inspect("--overwrite-dir", str(self.overwrite))
        self.assertEqual(before, self.input_snapshot(*roots))

    def test_oversize_text_marks_the_report_incomplete(self):
        self.file("High", "gamedata/scripts/large.script", "--" + "private" * 100)
        report, _ = self.inspect("--max-text-bytes", "32", status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(report["warnings"])
        self.assertNotIn("privateprivate", json.dumps(report))

    def test_binary_nul_text_is_not_parsed_as_lua(self):
        body = b"function binary.repeat_name() end\x00"
        self.file("High", "gamedata/scripts/a.script", body)
        self.file("Low", "gamedata/scripts/b.script", body)
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(report["warnings"])
        self.assertEqual(report["analysis"]["lua_function_repeats"], [])

    def test_path_like_ltx_names_are_omitted_and_marked_incomplete(self):
        private_path = str(self.base / "private-source-reference")
        self.file("High", "gamedata/configs/names.ltx",
                  f"[{private_path}]\nsetting = one\nsetting = two\n"
                  f"[scope]\n{private_path} = one\n{private_path} = two\n")
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(report["warnings"])
        self.assertEqual(report["analysis"]["ltx_duplicate_keys"], [])

    def test_unreadable_text_marks_the_report_incomplete(self):
        target = self.file("High", "gamedata/scripts/locked.script", "function locked.call() end")
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p]
            kernel.CreateFileW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.CreateFileW(str(target), 0x80000000, 0, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                self.skipTest("Could not create the synthetic exclusive file lock")
            try:
                report, _ = self.inspect(status=1)
            finally:
                kernel.CloseHandle(handle)
        else:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                self.skipTest("A privileged account bypasses the unreadable fixture permissions")
            target.chmod(0)
            try:
                report, _ = self.inspect(status=1)
            finally:
                target.chmod(0o600)
        self.assertFalse(report["summary"]["complete"])
        self.assertTrue(any(item["code"] == "unreadable_file" for item in report["warnings"]))

    def test_external_symbolic_links_are_skipped(self):
        outside = self.base / "outside"
        outside.mkdir()
        secret = outside / "private.script"
        secret.write_text("function never.expose() end", encoding="utf-8")
        linked_directory = self.mods / "High" / "linked"
        linked_file = self.mods / "Low" / "linked.script"
        try:
            linked_directory.symlink_to(outside, target_is_directory=True)
            linked_file.symlink_to(secret)
        except OSError:
            self.skipTest("Symbolic link creation is unavailable for this account")
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["loose_files"], 0)
        self.assertNotIn("never.expose", json.dumps(report))
        self.assertGreaterEqual(sum(item["code"] == "linked_path" for item in report["warnings"]), 2)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_windows_junction_is_skipped(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.script").write_text("function never.expose() end", encoding="utf-8")
        junction = self.mods / "High" / "linked"
        environment = dict(os.environ, MO2_TEST_JUNCTION=str(junction), MO2_TEST_TARGET=str(outside))
        created = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "New-Item -ItemType Junction -Path $env:MO2_TEST_JUNCTION "
             "-Target $env:MO2_TEST_TARGET -ErrorAction Stop | Out-Null"],
            env=environment, capture_output=True, text=True, timeout=30,
        )
        if created.returncode:
            self.skipTest("Junction creation is unavailable")
        def remove_fixture_junction():
            # Both names are fixed children of this test's TemporaryDirectory.
            # Remove the reparse point itself, never recursively delete its target.
            self.assertTrue(junction.absolute().is_relative_to(self.base.absolute()))
            self.assertTrue(outside.absolute().is_relative_to(self.base.absolute()))
            removed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "Remove-Item -LiteralPath $env:MO2_TEST_JUNCTION -Force -Confirm:$false -ErrorAction Stop"],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertTrue((outside / "private.script").is_file())

        self.addCleanup(remove_fixture_junction)
        report, _ = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["loose_files"], 0)
        self.assertNotIn("never.expose", json.dumps(report))

    def test_existing_output_is_never_overwritten(self):
        destination = self.base / "existing.json"
        sentinel = b"keep this unrelated report"
        destination.write_bytes(sentinel)
        process, _ = self.command(output=destination)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(destination.read_bytes(), sentinel)
        self.assertNotIn(str(self.base), process.stdout + process.stderr)

    def test_reserved_device_and_alternate_stream_outputs_are_refused(self):
        existing = self.base / "existing-file"
        existing.write_bytes(b"preserve ordinary file bytes")
        for destination in (self.base / "NUL.json", self.base / "CON",
                            Path(str(existing) + ":report.json")):
            with self.subTest(name=destination.name):
                process, _ = self.command(output=destination)
                self.assertEqual(process.returncode, 1)
                self.assertEqual(existing.read_bytes(), b"preserve ordinary file bytes")
                self.assertNotIn(str(self.base), process.stdout + process.stderr)
        self.assertFalse(Path(str(existing) + ":report.json").exists())

    def test_output_is_refused_inside_each_input_tree(self):
        for folder in (self.mods, self.overwrite):
            with self.subTest(folder=folder.name):
                destination = folder / "new-report.json"
                before = self.input_snapshot(self.mods, self.modlist, self.overwrite)
                process, _ = self.command("--overwrite-dir", str(self.overwrite), output=destination)
                self.assertEqual(process.returncode, 1)
                self.assertFalse(destination.exists())
                self.assertEqual(before, self.input_snapshot(self.mods, self.modlist, self.overwrite))

    def test_modlist_cannot_be_output(self):
        original = self.modlist.read_bytes()
        process, _ = self.command(output=self.modlist)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(self.modlist.read_bytes(), original)

    def test_modlist_hardlink_alias_cannot_be_output(self):
        original = self.modlist.read_bytes()
        alias = self.base / "alias.json"
        try:
            alias.hardlink_to(self.modlist)
        except OSError:
            self.skipTest("Hardlink creation is unavailable")
        process, _ = self.command(output=alias)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(alias.read_bytes(), original)
        self.assertEqual(self.modlist.read_bytes(), original)

    def test_symlinked_output_parent_is_refused(self):
        outside = self.base / "elsewhere"
        outside.mkdir()
        linked = self.base / "linked-output"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symbolic link creation is unavailable for this account")
        process, _ = self.command(output=linked / "report.json")
        self.assertEqual(process.returncode, 1)
        self.assertFalse((outside / "report.json").exists())

    def test_exit_codes_separate_findings_from_incomplete_scans(self):
        self.file("High", "same.bin", b"a")
        self.file("Low", "same.bin", b"b")
        report, _ = self.inspect()
        self.assertTrue(report["summary"]["complete"])
        report, _ = self.inspect("--fail-on-conflicts", status=2)
        self.assertGreater(report["summary"]["findings"], 0)
        self.set_modlist("+Missing", "+High", "+Low")
        report, _ = self.inspect("--fail-on-conflicts", status=1)
        self.assertFalse(report["summary"]["complete"])


if __name__ == "__main__":
    unittest.main()
