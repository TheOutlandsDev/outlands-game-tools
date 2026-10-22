"""Black-box CLI checks with synthetic Lua and MO2 fixtures only.

The scanned files deliberately contain runtime failures and a confined write
attempt: a syntax checker must compile them without running any of them.  These
tests never inspect an installed game or start a game, MO2, or a Lua command.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "lua_syntax.py"
RUNTIMES = ("luajit21", "lua51", "lua54")


def runtime_available(name):
    result = subprocess.run(
        [sys.executable, "-B", "-c",
         "import importlib, lupa; "
         "assert lupa.__version__ == '2.8'; "
         f"importlib.import_module('lupa.{name}')"],
        capture_output=True, text=True, timeout=20,
    )
    return result.returncode == 0


class FixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lua-syntax-tests-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source with spaces"
        self.source.mkdir()
        self.mods = self.base / "mods with spaces"
        self.mods.mkdir()
        self.modlist = self.base / "profile with spaces" / "modlist.txt"
        self.modlist.parent.mkdir()
        self.modlist.write_text("+High\n+Low\n", encoding="utf-8")
        for name in ("High", "Low"):
            (self.mods / name).mkdir()

    def file(self, relative, contents="return true\n", root=None):
        target = (root or self.source) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            target.write_bytes(contents)
        else:
            target.write_text(contents, encoding="utf-8")
        return target

    def invoke(self, *extra, mo2=False, no_site=False, timeout=20):
        arguments = (["--mods-dir", str(self.mods), "--modlist", str(self.modlist)]
                     if mo2 else ["--source-dir", str(self.source)])
        environment = dict(os.environ)
        if no_site:
            # -S plus no PYTHONPATH makes this an intentional missing-runtime
            # check even when the normal test runner uses a private dependency.
            environment.pop("PYTHONPATH", None)
        process = subprocess.run(
            [sys.executable, "-B", *(["-S"] if no_site else []),
             str(SCRIPT), *arguments, *map(str, extra)],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            timeout=timeout,
        )
        return process

    @classmethod
    def strings(cls, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from cls.strings(key)
                yield from cls.strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from cls.strings(item)

    def check_report(self, process, status=0, output=None):
        self.assertEqual(process.returncode, status, process.stdout + process.stderr)
        raw = output.read_text(encoding="utf-8") if output else process.stdout
        report = json.loads(raw)
        self.assertEqual(report["schema_version"], 1)
        public_text = "\n".join(self.strings(report)) + process.stdout + process.stderr
        self.assertNotIn(str(self.base), public_text)
        self.assertNotIn(self.base.as_posix(), public_text.replace("\\", "/"))
        return report

    def inspect(self, *extra, status=0, mo2=False):
        return self.check_report(self.invoke(*extra, mo2=mo2), status)

    @staticmethod
    def snapshot(*roots):
        result = {}
        for index, root in enumerate(roots):
            entries = [root] if root.is_file() else [root, *root.rglob("*")]
            for entry in entries:
                relative = "." if entry == root else entry.relative_to(root).as_posix()
                metadata = entry.stat()
                result[index, relative] = (
                    metadata.st_mtime_ns, metadata.st_size,
                    hashlib.sha256(entry.read_bytes()).hexdigest()
                    if entry.is_file() else None,
                )
        return result


class DependencyAndHelpTests(FixtureTests):
    def test_help_and_version_work_without_lupa(self):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        for option in ("--help", "--version"):
            process = subprocess.run(
                [sys.executable, "-B", "-S", str(SCRIPT), option],
                env=environment, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(process.stdout.strip())
            if option == "--help":
                for name in ("--source-dir", "--mods-dir", "--modlist", "--runtime",
                             "--output", "--max-script-bytes"):
                    self.assertIn(name, process.stdout)

    def test_missing_dependency_is_incomplete_without_fake_pass(self):
        self.file("safe.lua")
        report = self.check_report(self.invoke(no_site=True), 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 0)
        self.assertEqual(report["summary"]["checked_scripts"], 0)
        self.assertTrue(report["errors"])
        self.assertFalse(any(item["status"] == "PASS" for item in report["scripts"]))


class SyntaxCheckerCliTests(FixtureTests):
    @classmethod
    def setUpClass(cls):
        if not runtime_available("luajit21"):
            raise unittest.SkipTest("Install the pinned Lupa 2.8 dependency for parser tests")

    def test_valid_lua_and_script_extensions_are_checked(self):
        self.file("one.lua", "local answer = 42; return answer\n")
        self.file("nested/two.script", "function sample(value) return value + 1 end\n")
        self.file("ignored.txt", "not valid lua !")
        report = self.inspect()
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["effective_scripts"], 2)
        self.assertEqual(report["summary"]["checked_scripts"], 2)
        self.assertEqual(report["summary"]["passes"], 2)
        self.assertEqual({item["status"] for item in report["scripts"]}, {"PASS"})
        self.assertEqual(report["runtime"]["requested"], "luajit21")
        self.assertEqual(report["runtime"]["lupa_version"], "2.8")

    def test_scanned_source_is_never_executed(self):
        marker = self.base / "must-not-be-created.txt"
        # Lua supports escaped forward slashes on Windows paths too.  A broken
        # implementation could write only within this disposable fixture.
        literal = marker.as_posix().replace("\\", "\\\\").replace("'", "\\'")
        self.file("01-runtime-error.lua", "error('must not execute')\n")
        self.file("02-file-write.lua",
                  f"local f = assert(io.open('{literal}', 'w')); f:write('bad'); f:close()\n")
        command = (f'echo bad > "{marker}"').replace("\\", "\\\\").replace("'", "\\'")
        self.file("03-shell-command.lua", f"os.execute('{command}')\n")
        self.file("04-environment.lua", "return os.getenv('LUA_SYNTAX_PRIVATE_SENTINEL')\n")
        self.file("05-require.lua", "return require('module_that_does_not_exist_987')\n")
        self.file("06-infinite-loop.lua", "while true do end\n")
        before = self.snapshot(self.source)
        process = self.invoke(timeout=10)
        self.assertFalse(marker.exists(), "The checker executed scanned source")
        report = self.check_report(process)
        self.assertEqual(report["summary"]["passes"], 6)
        self.assertEqual(self.snapshot(self.source), before)

    def test_syntax_error_line_is_normalized_without_source_or_absolute_paths(self):
        secret = "PRIVATE_SOURCE_TOKEN_79367"
        self.file("broken.lua", f"-- heading\nlocal count = 1\nlocal value = function {secret}()\n")
        process = self.invoke()
        report = self.check_report(process, 2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["syntax_errors"], 1)
        failure, = report["scripts"]
        self.assertEqual(failure["status"], "SYNTAX_ERROR")
        self.assertEqual(failure["line"], 3)
        self.assertNotIn(secret, process.stdout + process.stderr)
        self.assertNotIn("local value", process.stdout + process.stderr)

    def test_repeated_inspection_is_deterministic(self):
        self.file("z.lua", "return 'last'\n")
        self.file("a.script", "return 'first'\n")
        first = self.inspect()
        second = self.inspect()
        self.assertEqual(first, second)
        self.assertEqual([item["path"] for item in first["scripts"]], ["a.script", "z.lua"])

    def test_bytecode_and_nul_bytes_are_rejected_without_compilation(self):
        self.file("lua-bytecode.lua", b"\x1bLua\x51\x00synthetic-do-not-load")
        self.file("luajit-bytecode.script", b"\x1bLJ\x02\x00synthetic-do-not-load")
        self.file("embedded-zero.lua", b"return 'safe'\x00error('do not execute')")
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_scripts"], 0)
        self.assertEqual(report["summary"]["skipped_scripts"], 3)
        self.assertEqual({item["status"] for item in report["scripts"]}, {"SKIPPED"})

    def test_utf8_bom_keeps_original_hash_and_separate_parser_hash(self):
        content = b"local name = 'synthetic'; return name\n"
        raw = b"\xef\xbb\xbf" + content
        source = self.file("with-bom.lua", raw)
        report = self.inspect()
        item, = report["scripts"]
        self.assertTrue(item["utf8_bom"])
        self.assertEqual(item["bytes"], len(raw))
        self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(item["parser_input_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(source.read_bytes(), raw)

    def test_empty_candidates_are_incomplete(self):
        self.file("readme.txt", "This is not a source candidate.")
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["effective_scripts"], 0)
        self.assertEqual(report["summary"]["passes"], 0)

    def test_default_size_limit_and_custom_limit(self):
        source = self.file("large.lua", b"--" + b"x" * 2097151)
        report = self.inspect(status=1)
        self.assertEqual(report["summary"]["checked_scripts"], 0)
        self.assertEqual(report["summary"]["skipped_scripts"], 1)
        source.write_bytes(b"return 1\n")
        report = self.inspect("--max-script-bytes", "8", status=1)
        self.assertEqual(report["summary"]["skipped_scripts"], 1)
        report = self.inspect("--max-script-bytes", "9")
        self.assertEqual(report["summary"]["passes"], 1)

    def test_invalid_or_unrepresentable_size_limits_fail_without_traceback(self):
        self.file("valid.lua")
        for value in ("0", "-1", str(sys.maxsize), str(10 ** 100)):
            with self.subTest(value=value):
                process = self.invoke("--max-script-bytes", value)
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                public_text = process.stdout + process.stderr
                self.assertNotIn("Traceback", public_text)
                self.assertNotIn("OverflowError", public_text)
                self.assertNotIn(str(self.base), public_text)

    def test_source_file_bytes_and_metadata_remain_unchanged(self):
        self.file("nested/a.lua", "local a = 1; return a\n")
        self.file("broken.script", "function bad(\n")
        before = self.snapshot(self.source)
        self.inspect(status=2)
        self.assertEqual(self.snapshot(self.source), before)

    def test_mo2_checks_only_highest_priority_winner(self):
        self.file("gamedata/scripts/same.script", "return true\n", self.mods / "High")
        self.file("gamedata/scripts/same.script", "function invalid(\n", self.mods / "Low")
        report = self.inspect(mo2=True)
        self.assertEqual(report["summary"]["loose_scripts"], 2)
        self.assertEqual(report["summary"]["effective_scripts"], 1)
        self.assertEqual(report["summary"]["shadowed_scripts"], 1)
        item, = report["scripts"]
        self.assertEqual(item["provider"], "High")
        self.assertEqual(item["status"], "PASS")

    def test_mo2_highest_winner_error_is_not_hidden_by_valid_lower_mod(self):
        self.file("same.lua", "function invalid(\n", self.mods / "High")
        self.file("same.lua", "return true\n", self.mods / "Low")
        report = self.inspect(mo2=True, status=2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["syntax_errors"], 1)
        self.assertEqual(report["scripts"][0]["provider"], "High")

    def test_base_and_overwrite_priority_and_input_immutability(self):
        base = self.base / "base game synthetic"
        overwrite = self.base / "overwrite synthetic"
        base.mkdir()
        overwrite.mkdir()
        self.file("same.script", "function invalid(\n", base)
        self.file("same.script", "function invalid(\n", self.mods / "High")
        self.file("same.script", "return true\n", overwrite)
        self.file("base-only.lua", "return 'base'\n", base)
        self.file("mod-only.lua", "return 'mod'\n", self.mods / "Low")
        before = self.snapshot(base, self.mods, self.modlist, overwrite)
        report = self.inspect("--base-dir", base, "--overwrite-dir", overwrite, mo2=True)
        self.assertEqual(report["summary"]["passes"], 3)
        winner = next(item for item in report["scripts"] if item["path"] == "same.script")
        self.assertEqual(winner["kind"], "overwrite")
        self.assertEqual(report["providers_priority_highest_first"][0]["kind"], "overwrite")
        self.assertEqual(report["providers_priority_highest_first"][-1]["kind"], "base")
        self.assertTrue(report["modlist"]["unchanged"])
        self.assertEqual(self.snapshot(base, self.mods, self.modlist, overwrite), before)

    def test_disabled_mods_separators_and_mohidden_are_not_checked(self):
        self.modlist.write_text("-Disabled\n+Group_separator\n+High\n", encoding="utf-8")
        self.file("hidden.lua", "function invalid(\n", self.mods / "Disabled")
        self.file("valid.lua", "return true\n", self.mods / "High")
        self.file("hidden.lua.mohidden", "function invalid(\n", self.mods / "High")
        self.file("folder.mohidden/invalid.lua", "function invalid(\n", self.mods / "High")
        report = self.inspect(mo2=True)
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual([item["path"] for item in report["scripts"]], ["valid.lua"])

    def test_missing_enabled_mod_makes_syntax_failure_incomplete(self):
        self.modlist.write_text("+Missing\n+High\n", encoding="utf-8")
        self.file("broken.lua", "function invalid(\n", self.mods / "High")
        report = self.inspect(mo2=True, status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["syntax_errors"], 1)

    def test_foreign_modlist_entry_cannot_escape_mods_directory(self):
        secret = "PRIVATE_OUTSIDE_SOURCE_387"
        self.file("private.lua", f"return '{secret}'\n", self.base / "outside")
        self.modlist.write_text("+../outside\n+High\n", encoding="utf-8")
        self.file("valid.lua", "return true\n", self.mods / "High")
        process = self.invoke(mo2=True)
        report = self.check_report(process, 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_scripts"], 1)
        self.assertNotIn(secret, process.stdout + process.stderr)

    def test_missing_source_root_is_incomplete(self):
        self.source.rmdir()
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 0)

    def test_symbolic_links_do_not_read_external_scripts(self):
        outside = self.base / "outside"
        external = self.file("private.lua", "function invalid(\n", outside)
        self.file("valid.lua")
        try:
            (self.source / "linked-directory").symlink_to(outside, target_is_directory=True)
            (self.source / "linked.lua").symlink_to(external)
        except OSError:
            self.skipTest("Symbolic link creation is unavailable for this account")
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_scripts"], 1)
        self.assertEqual(report["summary"]["syntax_errors"], 0)

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_windows_junction_is_not_followed(self):
        outside = self.base / "outside"
        external = self.file("private.lua", "function invalid(\n", outside)
        self.file("valid.lua")
        junction = self.source / "linked-directory"
        environment = dict(os.environ, LUA_TEST_JUNCTION=str(junction),
                           LUA_TEST_TARGET=str(outside))
        created = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "New-Item -ItemType Junction -Path $env:LUA_TEST_JUNCTION "
             "-Target $env:LUA_TEST_TARGET -ErrorAction Stop | Out-Null"],
            env=environment, capture_output=True, text=True, timeout=20,
        )
        if created.returncode:
            self.skipTest("Junction creation is unavailable")

        def remove_fixture_junction():
            # This removes the junction itself, never its target.  Validate both
            # absolute paths stay within the owned synthetic fixture first.
            fixture_root = self.base.resolve(strict=True)
            link = junction.parent.resolve(strict=True) / junction.name
            target = outside.resolve(strict=True)
            self.assertTrue(link.is_relative_to(fixture_root))
            self.assertTrue(target.is_relative_to(fixture_root))
            self.assertTrue(link.is_junction())
            self.assertEqual(link.resolve(strict=True), target)
            link.rmdir()
            self.assertFalse(link.exists())
            self.assertTrue(external.is_file())

        self.addCleanup(remove_fixture_junction)
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_scripts"], 1)
        self.assertEqual(report["summary"]["syntax_errors"], 0)

    def test_new_output_report_and_existing_output_protection(self):
        self.file("valid.lua")
        output = self.base / "report.json"
        process = self.invoke("--output", output)
        report = self.check_report(process, output=output)
        self.assertEqual(report["summary"]["passes"], 1)
        original = output.read_bytes()
        process = self.invoke("--output", output)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(output.read_bytes(), original)

    def test_output_cannot_be_placed_inside_source_tree(self):
        self.file("valid.lua")
        destination = self.source / "report.json"
        before = self.snapshot(self.source)
        process = self.invoke("--output", destination)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertFalse(destination.exists())
        self.assertEqual(self.snapshot(self.source), before)

    def test_output_cannot_replace_modlist_or_target_missing_parent(self):
        self.file("valid.lua", root=self.mods / "High")
        original = self.modlist.read_bytes()
        process = self.invoke("--output", self.modlist, mo2=True)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(self.modlist.read_bytes(), original)
        destination = self.base / "not-created" / "report.json"
        process = self.invoke("--output", destination, mo2=True)
        self.assertEqual(process.returncode, 1)
        self.assertFalse(destination.parent.exists())

    def test_output_symlink_parent_is_refused(self):
        self.file("valid.lua")
        outside = self.base / "outside"
        outside.mkdir()
        link = self.base / "linked-output"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symbolic link creation is unavailable for this account")
        process = self.invoke("--output", link / "report.json")
        self.assertEqual(process.returncode, 1)
        self.assertFalse((outside / "report.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows device and alternate-stream names")
    def test_windows_device_and_ads_output_paths_are_refused(self):
        self.file("valid.lua")
        for name in ("NUL", "CON.json", "report.json:private"):
            with self.subTest(name=name):
                process = self.invoke("--output", self.base / name)
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertFalse((self.base / "report.json").exists())

    def test_explicit_vm_selection_changes_accepted_language(self):
        self.file("lua54-only.lua", "return 7 // 2\n")
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime):
                if not runtime_available(runtime):
                    self.skipTest(f"Pinned Lupa runtime {runtime} is unavailable")
                expected = 0 if runtime == "lua54" else 2
                report = self.inspect("--runtime", runtime, status=expected)
                self.assertEqual(report["runtime"]["requested"], runtime)
                self.assertEqual(report["runtime"]["module"], f"lupa.{runtime}")
                self.assertEqual(report["summary"]["passes"], int(runtime == "lua54"))


if __name__ == "__main__":
    unittest.main()
