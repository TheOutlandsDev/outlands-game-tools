"""Black-box tests using only original generated text fixtures (MIT)."""
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

SCRIPT = Path(__file__).resolve().parents[1] / "ltx_inspector.py"
GENERATOR = SCRIPT.parent / "examples" / "create_example.py"
SPEC = importlib.util.spec_from_file_location("outlands_ltx_guard_test", SCRIPT)
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="outlands-ltx-", dir=os.environ.get("OUTLANDS_TEST_TMPDIR"))
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / "inputs"
        self.root.mkdir()

    def source(self, name, text, encoding="utf-8"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode(encoding))
        return path

    def invoke(self, *options, entries=("main.ltx",), expected=None):
        command = [sys.executable, "-B", str(SCRIPT), "--root", str(self.root)]
        for entry in entries:
            command.extend(["--entry", entry])
        result = subprocess.run(command + list(options), capture_output=True, text=True, timeout=30)
        if expected is not None:
            self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        report = json.loads(result.stdout) if result.stdout else None
        return result, report

    def codes(self, report, key="errors"):
        return {item["code"] for item in report[key]}

    def test_clean_include_and_parent_order(self):
        self.source("main.ltx", '#include "parts/base.ltx"\n[child]: second, first\nvalue = 42\n')
        self.source("parts/base.ltx", "[first]\n[second]\n")
        _, report = self.invoke(expected=0)
        self.assertTrue(report["complete"])
        child = next(item for item in report["definitions"] if item["section"] == "child")
        self.assertEqual(["second", "first"], child["parents"])
        self.assertEqual(2, report["summary"]["files_read"])

    def test_missing_parent_is_scoped_finding(self):
        self.source("main.ltx", "[child]: external_base\n")
        _, report = self.invoke(expected=2)
        self.assertTrue(report["complete"])
        self.assertEqual({"MISSING_PARENT"}, self.codes(report, "findings"))

    def test_multiple_entries_share_declaration_scope(self):
        self.source("main.ltx", "[child]: base\n")
        self.source("base.ini", "[base]\n")
        self.invoke(entries=("main.ltx", "base.ini"), expected=0)

    def test_duplicate_sections_case_normalized(self):
        self.source("main.ltx", "[Example]\n[example]\n")
        _, report = self.invoke(expected=2)
        self.assertEqual({"DUPLICATE_SECTION"}, self.codes(report, "findings"))
        self.assertEqual([1, 2], [item["line"] for item in report["findings"][0]["locations"]])

    def test_inheritance_cycle_and_self_cycle(self):
        self.source("main.ltx", "[a]: b\n[b]: a\n[self]: self\n")
        _, report = self.invoke(expected=2)
        self.assertEqual(2, len([item for item in report["findings"] if item["code"] == "INHERITANCE_CYCLE"]))

    def test_large_inheritance_graph_is_iterative(self):
        self.source("main.ltx", "".join(f"[s{i}]: s{i+1}\n" for i in range(2400)) + "[s2400]\n")
        _, report = self.invoke(expected=0)
        self.assertEqual(2401, report["summary"]["unique_sections"])

    def test_missing_include_is_incomplete_and_outranks_findings(self):
        self.source("main.ltx", '#include "absent.ltx"\n[child]: absent_parent\n')
        _, report = self.invoke(expected=1)
        self.assertFalse(report["complete"])
        self.assertIn("MISSING_FILE", self.codes(report))
        self.assertIn("MISSING_PARENT", self.codes(report, "findings"))

    def test_include_cycle_is_incomplete(self):
        self.source("main.ltx", '#include "child.ltx"\n[a]\n')
        self.source("child.ltx", '#include "main.ltx"\n[b]\n')
        _, report = self.invoke(expected=1)
        self.assertIn("INCLUDE_CYCLE", self.codes(report, "findings"))
        self.assertIn("INCLUDE_GRAPH_INCOMPLETE", self.codes(report))

    def test_repeated_include_is_review_finding_files_parsed_once(self):
        self.source("main.ltx", '#include "child.ltx"\n#include "child.ltx"\n[a]\n')
        self.source("child.ltx", "[b]\n")
        _, report = self.invoke(expected=2)
        self.assertEqual({"REPEATED_INCLUDE"}, self.codes(report, "findings"))
        self.assertEqual(2, report["summary"]["definitions"])

    def test_relative_parent_and_windows_separator_inside_root(self):
        self.source("parts/main.ltx", '#include "..\\base.ltx"\n[child]: base\n')
        self.source("base.ltx", "[base]\n")
        self.invoke(entries=("parts/main.ltx",), expected=0)

    def test_escaping_and_absolute_include_never_echoed(self):
        for include in ("../outside.ltx", "C:\\private\\outside.ltx", "//server/share/private.ltx"):
            with self.subTest(include=include):
                self.source("main.ltx", f'#include "{include}"\n[unused]\n')
                result, report = self.invoke(expected=1)
                self.assertIn("UNSAFE_PATH", self.codes(report))
                self.assertNotIn("private", result.stdout)
                self.assertNotIn("outside", result.stdout)

    def test_unsafe_entry(self):
        self.source("main.ltx", "[a]\n")
        for entry in ("../main.ltx", "./main.ltx", "/main.ltx", "C:main.ltx", "CON.ltx"):
            with self.subTest(entry=entry):
                _, report = self.invoke(entries=(entry,), expected=1)
                self.assertIn("UNSAFE_PATH", self.codes(report))

    def test_duplicate_entries_rejected(self):
        self.source("main.ltx", "[a]\n")
        _, report = self.invoke(entries=("main.ltx", "MAIN.LTX"), expected=1)
        self.assertIn("DUPLICATE_ENTRY", self.codes(report))

    def test_directory_lookup_budget_with_small_original_fixture(self):
        self.source("main.ltx", "[a]\n")
        self.source("one.ltx", "[b]\n")
        self.source("two.ltx", "[c]\n")
        for name in ("outside-one", "outside-two", "outside-three"):
            (self.work / name).write_text("original", encoding="utf-8")
        with patch.object(INSPECTOR, "MAX_DIRECTORY_ENTRIES", 2):
            with self.assertRaises(INSPECTOR.CheckError) as rejected:
                INSPECTOR.checked_child(self.root, "main.ltx")
            self.assertEqual("DIRECTORY_ENTRY_LIMIT", rejected.exception.code)
            output = self.work / "limited-report.json"
            with self.assertRaises(INSPECTOR.CheckError) as rejected:
                INSPECTOR.write_report(str(output), str(self.root), "{}\n")
            self.assertEqual("DIRECTORY_ENTRY_LIMIT", rejected.exception.code)
            self.assertNotIn("limited-report.json", {item.name for item in self.work.iterdir()})

    def test_reserved_windows_devices_rejected_before_io(self):
        self.source("main.ltx", "[a]\n")
        devices = ("NUL", "CONIN$", "CONOUT$", "CLOCK$", "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³")
        for device in devices:
            with self.subTest(device=device):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", device,
                                         "--entry", "main.ltx"], capture_output=True, text=True, timeout=30)
                self.assertEqual(1, result.returncode)
                self.assertIn("UNSAFE_PATH", self.codes(json.loads(result.stdout)))
                _, report = self.invoke(entries=(device + ".ltx",), expected=1)
                self.assertIn("UNSAFE_PATH", self.codes(report))
                before = {item.name for item in self.work.iterdir()}
                output_result, _ = self.invoke("--output", str(self.work / device), expected=1)
                self.assertIn("UNSAFE_PATH", output_result.stderr)
                self.assertEqual(before, {item.name for item in self.work.iterdir()})

    def test_wildcard_include_is_incomplete(self):
        self.source("main.ltx", '#include "*.ltx"\n[a]\n')
        _, report = self.invoke(expected=1)
        self.assertIn("UNSAFE_PATH", self.codes(report))

    def test_dltx_and_unknown_directives_incomplete(self):
        for line in ("![a]", "@[a]", ">[a]", "[a]:!base", "#define SOMETHING", "!key = 2"):
            with self.subTest(line=line):
                self.source("main.ltx", "[before]\n" + line + "\n[after]\n")
                _, report = self.invoke(expected=1)
                self.assertEqual(["before"], [item["section"] for item in report["definitions"]])

    def test_multiline_or_escaped_quote_stops_file(self):
        for line in ('key = "open', 'key = "escaped\\"quote"'):
            self.source("main.ltx", "[before]\n" + line + "\n[after]\n")
            _, report = self.invoke(expected=1)
            self.assertEqual(["before"], [item["section"] for item in report["definitions"]])

    def test_comments_and_quoted_semicolon_or_slash(self):
        self.source("main.ltx", '; comment\n// comment\n[a] ; section\nkey = "semi;slash//text" ; end\nlist_item\n$spawn = text\n')
        self.invoke(expected=0)

    def test_values_comments_and_absolute_root_are_not_reported(self):
        private = "PRIVATE_VALUE_937ab1"
        self.source("main.ltx", f"[a]\nkey = {private}\n; {private}\n")
        result, _ = self.invoke(expected=0)
        self.assertNotIn(private, result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    def test_bom_and_explicit_cp1251(self):
        self.source("main.ltx", "\ufeff[a]\nkey = привет\n")
        self.invoke(expected=0)
        self.source("main.ltx", "[a]\nkey = привет\n", "cp1251")
        _, report = self.invoke(expected=1)
        self.assertIn("ENCODING_ERROR", self.codes(report))
        self.invoke("--encoding", "cp1251", expected=0)

    def test_binary_control_character(self):
        self.source("main.ltx", "[a]\nkey = \x00secret\n")
        result, report = self.invoke(expected=1)
        self.assertIn("UNSUPPORTED_CONTROL_CHARACTER", self.codes(report))
        self.assertNotIn("secret", result.stdout)

    def test_file_and_total_byte_limits(self):
        self.source("main.ltx", '#include "child.ltx"\n[a]\n')
        self.source("child.ltx", "[b]\n" + "; padding\n" * 30)
        _, report = self.invoke("--max-file-bytes", "40", expected=1)
        self.assertIn("FILE_BYTE_LIMIT", self.codes(report))
        _, report = self.invoke("--max-total-bytes", "40", expected=1)
        self.assertIn("TOTAL_BYTE_LIMIT", self.codes(report))
        self.assertLessEqual(report["summary"]["bytes_read"], 40)

    def test_file_count_and_depth_limits(self):
        self.source("main.ltx", '#include "child.ltx"\n[a]\n')
        self.source("child.ltx", '#include "last.ltx"\n[b]\n')
        self.source("last.ltx", "[c]\n")
        _, report = self.invoke("--max-files", "1", expected=1)
        self.assertIn("FILE_COUNT_LIMIT", self.codes(report))
        _, report = self.invoke("--max-depth", "1", expected=1)
        self.assertIn("INCLUDE_DEPTH_LIMIT", self.codes(report))

    def test_limits_reject_zero_negative_and_oversized(self):
        self.source("main.ltx", "[a]\n")
        for value in ("0", "-1", str(sys.maxsize), "9999999999999999999999999999999", "x"):
            result, report = self.invoke("--max-files", value, expected=1)
            self.assertIsNone(report)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("INVALID_ARGUMENTS", result.stderr)

    def test_record_budget_limits_parent_fanout(self):
        self.source("main.ltx", "[a]: b, c, d\n[b]\n[c]\n[d]\n")
        _, report = self.invoke("--max-records", "3", expected=1)
        self.assertIn("RECORD_COUNT_LIMIT", self.codes(report))
        self.assertEqual([], report["definitions"])

    def test_cycle_report_budget_is_incomplete(self):
        # Many back edges can otherwise repeat a long active path quadratically.
        self.source("main.ltx", "[a]: b\n[b]: c, a\n[c]: d, a\n[d]: a\n")
        _, report = self.invoke("--max-records", "10", expected=1)
        self.assertIn("CYCLE_REPORT_LIMIT", self.codes(report))

    def test_dense_back_edges_are_bounded_with_default_limits(self):
        self.source("main.ltx", "".join(f"[s{i}]: s{i+1}, s0\n" for i in range(600)) + "[s600]: s0\n")
        result, report = self.invoke(expected=1)
        self.assertIn("CYCLE_REPORT_LIMIT", self.codes(report))
        self.assertLess(len(result.stdout), 3_000_000)
        self.assertFalse(report["complete"])

    def test_report_expansion_budget_returns_small_incomplete_report(self):
        self.source("main.ltx", "".join(f"[section_{i}]\n" for i in range(100)))
        result, report = self.invoke("--max-report-bytes", "2000", expected=1)
        self.assertEqual({"REPORT_BYTE_LIMIT"}, self.codes(report))
        self.assertEqual([], report["definitions"])
        self.assertLess(len(result.stdout), 2000)

    def test_long_identifiers_cannot_multiply_cycle_output_without_bound(self):
        names = [f"section_{index}_" + "x" * 2000 for index in range(81)]
        text = "".join(f"[{names[index]}]: {names[index+1]}, {names[0]}\n" for index in range(80))
        self.source("main.ltx", text + f"[{names[80]}]: {names[0]}\n")
        result, report = self.invoke(expected=1)
        self.assertIn("CYCLE_REPORT_LIMIT", self.codes(report))
        self.assertLess(len(result.stdout), 5_000_000)

    def test_empty_scope_is_incomplete(self):
        self.source("main.ltx", "; only a comment\n")
        _, report = self.invoke(expected=1)
        self.assertIn("NO_DEFINITIONS", self.codes(report))

    def test_input_bytes_unchanged(self):
        self.source("main.ltx", '#include "child.ltx"\n[a]: b\nkey = original\n')
        self.source("child.ltx", "[b]\n")
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in self.root.rglob("*") if path.is_file()}
        self.invoke(expected=0)
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_exclusive_output_and_input_root_guard(self):
        self.source("main.ltx", "[a]\n")
        output = self.work / "report.json"
        result, report = self.invoke("--output", str(output), expected=0)
        self.assertIsNone(report)
        self.assertEqual(0, json.loads(output.read_text())["exit_code"])
        before = output.read_bytes()
        result, _ = self.invoke("--output", str(output), expected=1)
        self.assertIn("OUTPUT_EXISTS", result.stderr)
        self.assertEqual(before, output.read_bytes())
        result, _ = self.invoke("--output", str(self.root / "report.json"), expected=1)
        self.assertIn("OUTPUT_INSIDE_INPUT_ROOT", result.stderr)
        self.assertFalse((self.root / "report.json").exists())

    def test_output_device_name_and_missing_parent_rejected(self):
        self.source("main.ltx", "[a]\n")
        for output in (self.work / "CON.json", self.work / "absent" / "report.json"):
            result, _ = self.invoke("--output", str(output), expected=1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())

    def test_output_link_parent_rejected(self):
        self.source("main.ltx", "[a]\n")
        target = self.work / "actual"
        target.mkdir()
        link = self.work / "alias"
        self.make_directory_link(link, target)
        try:
            result, _ = self.invoke("--output", str(link / "report.json"), expected=1)
            self.assertIn("LINK_OR_REPARSE_POINT", result.stderr)
            self.assertFalse((target / "report.json").exists())
        finally:
            link.rmdir() if os.name == "nt" else link.unlink()

    def make_directory_link(self, link, target):
        if os.name == "nt":
            # Paths travel as environment values; none are interpolated into shell code.
            environment = dict(os.environ, OUTLANDS_LTX_JUNCTION_LINK=str(link),
                               OUTLANDS_LTX_JUNCTION_TARGET=str(target))
            command = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                       "New-Item -ItemType Junction -Path $env:OUTLANDS_LTX_JUNCTION_LINK -Target $env:OUTLANDS_LTX_JUNCTION_TARGET -ErrorAction Stop | Out-Null"]
            created = subprocess.run(command, capture_output=True, text=True, timeout=30, env=environment)
            if created.returncode:
                self.skipTest("Windows junction creation unavailable in this test environment")
        else:
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlink creation unavailable in this test environment")

    def test_input_junction_or_symlink_rejected(self):
        target = self.work / "external"
        target.mkdir()
        (target / "private.ltx").write_text("[private]\n", encoding="utf-8")
        self.source("main.ltx", '#include "alias/private.ltx"\n[a]\n')
        link = self.root / "alias"
        self.make_directory_link(link, target)
        try:
            _, report = self.invoke(expected=1)
            self.assertIn("LINK_OR_REPARSE_POINT", self.codes(report))
            self.assertNotIn("private", {item["section"] for item in report["definitions"]})
        finally:
            link.rmdir() if os.name == "nt" else link.unlink()

    @unittest.skipIf(os.name == "nt", "Windows normal directories cannot contain case-only filename pairs")
    def test_case_ambiguity(self):
        self.source("main.ltx", "[a]\n")
        self.source("MAIN.LTX", "[b]\n")
        _, report = self.invoke(expected=1)
        self.assertIn("CASE_AMBIGUITY", self.codes(report))

    def test_case_mismatch_rejected_consistently(self):
        self.source("main.ltx", '#include "BASE.LTX"\n[a]\n')
        self.source("base.ltx", "[b]\n")
        _, report = self.invoke(expected=1)
        self.assertIn("CASE_MISMATCH", self.codes(report))

    def test_stdlib_only_under_no_site_packages(self):
        self.source("main.ltx", "[a]\n")
        result = subprocess.run([sys.executable, "-S", "-B", str(SCRIPT), "--root", str(self.root), "--entry", "main.ltx"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_generated_example(self):
        destination = self.work / "demo"
        result = subprocess.run([sys.executable, "-B", str(GENERATOR), "--destination", str(destination)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.root = destination / "configs"
        _, report = self.invoke(entries=("clean.ltx",), expected=0)
        self.assertEqual(3, report["summary"]["unique_sections"])
        self.invoke(entries=("review.ltx",), expected=2)
        self.invoke(entries=("unsupported.ltx",), expected=1)
        rerun = subprocess.run([sys.executable, "-B", str(GENERATOR), "--destination", str(destination)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(1, rerun.returncode)


if __name__ == "__main__":
    unittest.main()
