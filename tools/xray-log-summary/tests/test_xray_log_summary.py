"""Black-box checks using generated text only; no actual game logs. MIT."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "xray_log_summary.py"


class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xray-test-")
        self.root = Path(self.temporary.name)
        self.log = self.root / "generated.log"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(self, data: bytes | None = b"ordinary status\n", *extra: str,
                 log: Path | str | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        if data is not None:
            self.log.write_bytes(data)
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--log",
                                 str(self.log if log is None else log), *extra],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.stderr, "", result.stderr)
        return result, json.loads(result.stdout)

    def category(self, report: dict, code: str) -> dict:
        return next(row for row in report["categories"] if row["code"] == code)

    def test_clean_nonempty_log(self) -> None:
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["lines_read"], 1)
        self.assertFalse(report["summary"]["has_findings"])

    def test_fatal_late_in_log_is_not_missed(self) -> None:
        result, report = self.run_tool(b"ok\n" * 5000 + b"FATAL ERROR\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.category(report, "fatal_error")["line_numbers"], [5001])

    def test_script_error_and_runtime_variants(self) -> None:
        result, report = self.run_tool(b"[SCRIPT ERROR] custom text\n! SCRIPT RUNTIME ERROR\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["summary"]["script_errors"], 2)
        self.assertEqual(report["summary"]["warnings"], 0)

    def test_repeated_audio_warning(self) -> None:
        result, report = self.run_tool(b"! Sound sampling warning: generated value\n" * 7)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.category(report, "audio_warning")["count"], 7)
        self.assertEqual(self.category(report, "audio_warning")["line_numbers"], list(range(1, 8)))

    def test_treasure_and_other_warning_categories(self) -> None:
        result, report = self.run_tool(b"WARNING treasure item missing: generated_item\nWARNING arbitrary condition\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.category(report, "missing_treasure_item_warning")["count"], 1)
        self.assertEqual(self.category(report, "other_warning")["count"], 1)

    def test_warning_precedence_is_mutually_exclusive(self) -> None:
        _, report = self.run_tool(b"! FATAL ERROR sound warning\n! [SCRIPT ERROR] warning\nWARNING sound treasure item missing\n")
        self.assertEqual(report["summary"]["fatal_errors"], 1)
        self.assertEqual(report["summary"]["script_errors"], 1)
        self.assertEqual(report["summary"]["warnings"], 1)
        self.assertEqual(self.category(report, "audio_warning")["count"], 1)

    def test_marker_flags_observe_text_only(self) -> None:
        result, report = self.run_tool(b"Starting engine\nStarting new game\nGameNetworkingSockets\nClient connected\nEngine shutdown\n")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(all(report["markers"].values()))
        self.assertEqual(report["summary"]["warnings"], 0)

    def test_privacy_omits_all_original_values(self) -> None:
        private_path = "C:" + "\\" + "Users" + "\\" + "SyntheticPerson" + "\\" + "private.log"
        endpoint = ".".join(("192", "168", "7", "49")) + ":27015"
        secret = "gh" + "p_" + "s" * 36
        values = [private_path, endpoint, secret, "PrivatePlayerName", "unique_actor_item_78"]
        source = ("WARNING sound " + " ".join(values) + "\nFATAL ERROR " + secret + "\n").encode()
        result, report = self.run_tool(source)
        self.assertEqual(result.returncode, 2)
        for value in values:
            self.assertNotIn(value, result.stdout)
        self.assertNotIn(str(self.log), result.stdout)
        self.assertEqual(report["summary"]["fatal_errors"], 1)

    def test_line_number_lists_are_capped_without_losing_counts(self) -> None:
        result, report = self.run_tool(b"WARNING repeated condition\n" * 1100)
        self.assertEqual(result.returncode, 2)
        category = self.category(report, "other_warning")
        self.assertEqual(category["count"], 1100)
        self.assertEqual(category["line_numbers"], list(range(1, 1001)))
        self.assertTrue(category["line_numbers_truncated"])

    def test_final_line_without_newline(self) -> None:
        result, report = self.run_tool(b"ok\nFATAL ERROR")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["summary"]["lines_read"], 2)

    def test_utf8_bom_and_crlf(self) -> None:
        result, report = self.run_tool(b"\xef\xbb\xbf! Sound warning\r\nok\r\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["summary"]["lines_read"], 2)
        self.assertEqual(self.category(report, "audio_warning")["count"], 1)

    def test_cp1251_explicit(self) -> None:
        data = "WARNING sound: синтетический пример\n".encode("cp1251")
        result, report = self.run_tool(data, "--encoding", "cp1251")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["options"]["encoding"], "cp1251")
        self.assertNotIn("синтетический", result.stdout)

    def test_invalid_utf8_stops_before_later_fatal(self) -> None:
        result, report = self.run_tool(b"ok\n\xff\nFATAL ERROR\n")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["errors"], [{"code": "decoding_error", "line": 2}])
        self.assertEqual(report["summary"]["fatal_errors"], 0)

    def test_incomplete_outranks_existing_finding(self) -> None:
        result, report = self.run_tool(b"FATAL ERROR\n\xff\n")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["summary"]["has_findings"])

    def test_binary_nul_is_incomplete(self) -> None:
        result, report = self.run_tool(b"ordinary\x00bytes\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "binary_log")

    def test_empty_log_is_incomplete(self) -> None:
        result, report = self.run_tool(b"")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "empty_log")

    def test_byte_limit_refuses_oversized_file_before_scan(self) -> None:
        result, report = self.run_tool(b"FATAL ERROR\n", "--max-bytes", "5")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "byte_limit")
        self.assertEqual(report["summary"]["bytes_read"], 0)

    def test_exact_byte_and_line_byte_limits_pass(self) -> None:
        result, report = self.run_tool(b"ok\n", "--max-bytes", "3", "--max-line-bytes", "3", "--max-lines", "1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["summary"]["bytes_read"], 3)

    def test_long_line_is_incomplete_and_not_classified(self) -> None:
        result, report = self.run_tool(b"FATAL ERROR long\n", "--max-line-bytes", "8")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"], [{"code": "line_byte_limit", "line": 1}])
        self.assertEqual(report["summary"]["fatal_errors"], 0)

    def test_line_count_limit_is_incomplete(self) -> None:
        result, report = self.run_tool(b"ok\nFATAL ERROR\n", "--max-lines", "1")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"], [{"code": "line_count_limit", "line": 2}])
        self.assertEqual(report["summary"]["lines_read"], 1)

    def test_missing_input_omits_path(self) -> None:
        missing = self.root / "private-missing.log"
        result, report = self.run_tool(None, log=missing)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(str(missing), result.stdout)
        self.assertEqual(report["errors"][0]["code"], "missing_path")

    def test_directory_input_refused(self) -> None:
        result, report = self.run_tool(None, log=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "nonregular_input")

    def test_network_and_device_paths_refused(self) -> None:
        for value in ("//server/share/example.log", "\\\\server\\share\\example.log", "NUL", "CON.txt", "C:relative.log"):
            with self.subTest(value=value):
                result, report = self.run_tool(None, log=value)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["errors"][0]["code"], "unsupported_path")
                self.assertNotIn(value, result.stdout)

    def test_invalid_limit_arguments_are_sanitized(self) -> None:
        for value in ("0", "-1", "abc", str(sys.maxsize), "9" * 5000):
            with self.subTest(value=value[:20]):
                result, report = self.run_tool(b"ok\n", "--max-lines", value)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["errors"][0]["code"], "invalid_arguments")

    def test_unknown_argument_and_encoding_are_sanitized(self) -> None:
        for args in (("--private-unknown", "sensitive-value"), ("--encoding", "invalid-private-encoding")):
            result, report = self.run_tool(b"ok\n", *args)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(report["errors"][0]["code"], "invalid_arguments")
            self.assertNotIn(args[-1], result.stdout)

    def test_multiple_logs_are_rejected_instead_of_silently_using_last(self) -> None:
        other = self.root / "second-private.log"
        other.write_bytes(b"FATAL ERROR\n")
        result, report = self.run_tool(b"ok\n", "--log", str(other))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "invalid_arguments")
        self.assertNotIn(str(other), result.stdout)

    def test_input_hash_and_mtime_unchanged(self) -> None:
        data = b"WARNING sound generated\nFATAL ERROR\n"
        self.log.write_bytes(data)
        before = self.log.stat()
        digest = hashlib.sha256(data).hexdigest()
        result, _ = self.run_tool(None)
        after = self.log.stat()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(hashlib.sha256(self.log.read_bytes()).hexdigest(), digest)
        self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))

    def test_output_is_new_report_matching_stdout(self) -> None:
        output = self.root / "report.json"
        result, report = self.run_tool(b"WARNING generated\n", "--output", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)

    def test_existing_output_is_protected(self) -> None:
        output = self.root / "report.json"
        output.write_bytes(b"keep this exact file")
        result, report = self.run_tool(b"ok\n", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "output_exists")
        self.assertEqual(output.read_bytes(), b"keep this exact file")

    def test_output_input_is_protected(self) -> None:
        data = b"WARNING generated\n"
        result, report = self.run_tool(data, "--output", str(self.log))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["errors"][0]["code"], "output_is_input")
        self.assertEqual(self.log.read_bytes(), data)

    def test_output_parent_must_exist(self) -> None:
        output = self.root / "missing" / "report.json"
        result, report = self.run_tool(b"ok\n", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.parent.exists())

    def test_incomplete_scan_can_be_saved(self) -> None:
        output = self.root / "report.json"
        result, report = self.run_tool(b"FATAL ERROR\n\xff\n", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)

    def test_linked_input_and_ancestor_are_refused(self) -> None:
        self.log.write_bytes(b"FATAL ERROR\n")
        link = self.root / "linked.log"
        linked_dir = self.root / "linked-dir"
        try:
            link.symlink_to(self.log)
            linked_dir.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            if link.is_symlink():
                link.unlink()
            self.skipTest("Native symlink creation unavailable; junction test covers Windows ancestors")
        try:
            for source in (link, linked_dir / self.log.name):
                result, report = self.run_tool(None, log=source)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["errors"][0]["code"], "linked_path")
        finally:
            link.unlink()
            linked_dir.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows junction coverage")
    def test_windows_junction_input_and_output_parent_refused(self) -> None:
        target = self.root / "physical"
        target.mkdir()
        source = target / "generated.log"
        source.write_bytes(b"FATAL ERROR\n")
        junction = self.root / "junction"
        def ps_quote(value: Path) -> str:
            return "'" + str(value).replace("'", "''") + "'"
        command = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path " + ps_quote(junction) + " -Target " + ps_quote(target) + " | Out-Null"
        created = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=20)
        if created.returncode != 0:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("Windows CI must execute the native junction coverage")
            self.skipTest("Native junction creation unavailable in this Windows account/sandbox")
        try:
            result, report = self.run_tool(None, log=junction / source.name)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(report["errors"][0]["code"], "linked_path")
            result, report = self.run_tool(b"ok\n", "--output", str(junction / "report.json"))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(report["errors"][0]["code"], "linked_path")
            self.assertFalse((target / "report.json").exists())
        finally:
            # Removing this one reparse-point directory must not recurse into target.
            self.assertTrue(junction.is_junction())
            junction.rmdir()
        self.assertEqual(source.read_bytes(), b"FATAL ERROR\n")

    def test_example_generator_is_exclusive_and_example_has_expected_findings(self) -> None:
        generator = SCRIPT.parent / "examples" / "create_example.py"
        destination = self.root / "example.log"
        command = [sys.executable, "-B", str(generator), "--output", str(destination)]
        first = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(first.returncode, 0)
        data = destination.read_bytes()
        result, report = self.run_tool(None, log=destination)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["summary"]["fatal_errors"], 1)
        self.assertEqual(report["summary"]["script_errors"], 1)
        self.assertEqual(report["summary"]["warnings"], 4)
        second = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(second.returncode, 1)
        self.assertEqual(destination.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
