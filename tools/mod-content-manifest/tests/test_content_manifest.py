"""Black-box checks with original generated trees and editable toy manifests. MIT."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "content_manifest.py"
EXAMPLE = SCRIPT.parent / "examples" / "create_example.py"


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="manifest-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def put(self, relative: str, data: bytes = b"original toy bytes\n", *,
            root: Path | None = None) -> Path:
        path = (self.source if root is None else root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_tool(self, *args: object) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                                capture_output=True, text=True, timeout=30)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)
        payload = result.stdout
        if not payload.strip() and "--output" in args:
            output = Path(args[args.index("--output") + 1])
            if output.is_file():
                payload = output.read_text(encoding="utf-8")
        self.assertTrue(payload.strip(), result.stderr)
        report = json.loads(payload)
        self.assertNotIn(str(self.root), payload)
        return result, report

    def scan(self, *args: object, source: Path | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.run_tool("scan", "--source-dir", self.source if source is None else source, *args)

    def save(self, name: str, report: dict) -> Path:
        target = self.root / name
        target.write_text(json.dumps(report), encoding="utf-8")
        return target

    def diff(self, baseline: dict, candidate: dict, *args: object) -> tuple[subprocess.CompletedProcess[str], dict]:
        left = self.save("baseline.json", baseline)
        right = self.save("candidate.json", candidate)
        return self.run_tool("diff", "--baseline", left, "--candidate", right, *args)

    def snapshot(self, root: Path) -> dict[str, str]:
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*") if path.is_file()}

    def valid_manifest(self) -> dict:
        self.put("gamedata/configs/toy.ltx", b"[toy]\nvalue = 1\n")
        result, report = self.scan()
        self.assertEqual(result.returncode, 0, report)
        return report

    def mo2(self, *, overwrite: bool = False, missing: bool = False) -> tuple[Path, Path, Path, Path]:
        mods = self.root / "mods"
        mods.mkdir()
        self.put("High Toy/gamedata/configs/shared.ltx", b"high", root=mods)
        self.put("Low Toy/gamedata/configs/shared.ltx", b"low", root=mods)
        self.put("Low Toy/gamedata/configs/low.ltx", b"unique-low", root=mods)
        self.put("Disabled Toy/gamedata/configs/disabled.ltx", b"disabled", root=mods)
        self.put("High Toy/meta.ini", b"local provider metadata", root=mods)
        self.put("High Toy/gamedata/configs/hidden.ltx.mohidden", b"hidden", root=mods)
        base = self.root / "base"
        self.put("gamedata/configs/shared.ltx", b"base", root=base)
        self.put("gamedata/configs/base.ltx", b"unique-base", root=base)
        extra = self.root / "overwrite"
        if overwrite:
            self.put("gamedata/configs/shared.ltx", b"overwrite", root=extra)
        modlist = self.root / "modlist.txt"
        modlist.write_text("\ufeff# native saved order: highest first\n+High Toy\n+Low Toy\n-Disabled Toy\n-Absent Disabled\n" +
                           ("+Absent Enabled\n" if missing else ""), encoding="utf-8")
        return mods, modlist, base, extra

    def test_directory_hashes_include_empty_and_arbitrary_binary(self) -> None:
        self.put("empty.bin", b"")
        self.put("nested/toy.dat", bytes(range(256)) * 20)
        result, report = self.scan()
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["complete"])
        rows = {row["path"]: row for row in report["files"]}
        self.assertEqual(rows["empty.bin"]["sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(rows["nested/toy.dat"]["bytes"], 5120)
        self.assertEqual(rows["nested/toy.dat"]["sha256"], hashlib.sha256(bytes(range(256)) * 20).hexdigest())
        self.assertEqual(report["summary"]["files"], 2)
        self.assertEqual(report["summary"]["bytes"], 5120)

    def test_scan_is_deterministic_without_absolute_roots(self) -> None:
        self.put("gamedata/configs/Z.ltx", b"z")
        self.put("gamedata/configs/a.ltx", b"a")
        _, first = self.scan()
        other = self.root / "other"
        self.put("gamedata/configs/a.ltx", b"a", root=other)
        self.put("gamedata/configs/Z.ltx", b"z", root=other)
        _, second = self.scan(source=other)
        self.assertEqual(first, second)

    def test_scan_preserves_source_bytes_and_file_selection(self) -> None:
        self.put("gamedata/toy.ltx", b"[toy]\nvalue = 2\n")
        self.put("saves/toy-private.dat", b"toy private save marker")
        before = self.snapshot(self.source)
        result, _ = self.scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot(self.source))

    def test_extension_filter_is_case_insensitive_and_deterministic(self) -> None:
        self.put("upper.LTX", b"one")
        self.put("nested/lower.script", b"two")
        self.put("ignored.txt", b"three")
        result, report = self.scan("--extensions", ".script", "--extensions", ".LTX")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["selection"]["extensions"], [".ltx", ".script"])
        self.assertEqual({row["path"] for row in report["files"]}, {"upper.LTX", "nested/lower.script"})

    def test_default_exclusions_hide_names_and_contents(self) -> None:
        secret_name = "unshared-local-save-name"
        marker = "toy-secret-content-keep-local"
        for relative in (f"saves/{secret_name}.dat", "logs/private.log", ".git/config",
                         ".env", ".env.local", "nested/secret.pem", "credentials.json"):
            self.put(relative, marker.encode())
        self.put("gamedata/public.ltx", b"[toy]\nvalue = yes\n")
        result, report = self.scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual([row["path"] for row in report["files"]], ["gamedata/public.ltx"])
        self.assertNotIn(secret_name, result.stdout)
        self.assertNotIn(marker, result.stdout)
        self.assertGreaterEqual(report["summary"]["excluded_entries"], 7)

    def test_content_is_not_included_in_manifest(self) -> None:
        marker = b"original-private-looking-text-never-echo-this"
        self.put("gamedata/toy.ltx", marker)
        result, report = self.scan()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(marker.decode(), result.stdout)
        self.assertEqual(report["files"][0]["sha256"], hashlib.sha256(marker).hexdigest())

    def test_unicode_relative_names_are_preserved(self) -> None:
        self.put("gamedata/configs/caf\u00e9.ltx", b"toy")
        result, report = self.scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["files"][0]["path"], "gamedata/configs/caf\u00e9.ltx")

    def test_per_file_total_filecount_and_entry_caps_are_incomplete(self) -> None:
        self.put("nested/one.dat", b"a" * 5)
        self.put("nested/two.dat", b"b" * 5)
        for option, value in (("--max-file-bytes", 4), ("--max-total-bytes", 9),
                              ("--max-files", 1), ("--max-entries", 1)):
            with self.subTest(option=option):
                result, report = self.scan(option, value)
                self.assertEqual(result.returncode, 1, report)
                self.assertFalse(report["complete"])
                self.assertTrue(report["errors"])

    def test_invalid_integer_limits_fail_without_traceback(self) -> None:
        self.put("toy.dat")
        for value in ("0", "-1", "not-an-integer", str(sys.maxsize + 1), "9" * 500):
            with self.subTest(value=value[:30]):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "scan", "--source-dir",
                                         str(self.source), "--max-file-bytes", value],
                                        capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)

    def test_existing_output_is_never_overwritten(self) -> None:
        self.put("toy.dat")
        output = self.root / "existing.json"
        output.write_bytes(b"keep this original output")
        result, report = self.scan("--output", output)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertEqual(output.read_bytes(), b"keep this original output")

    def test_excessive_extension_arguments_are_incomplete(self) -> None:
        self.put("toy.ltx")
        arguments = [value for _ in range(1001) for value in ("--extensions", ".ltx")]
        result, report = self.scan(*arguments)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_output_inside_source_is_rejected_without_creation(self) -> None:
        self.put("toy.dat")
        output = self.source / "report.json"
        result, report = self.scan("--output", output)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertFalse(output.exists())

    def test_new_output_contains_valid_manifest_without_extra_stdout(self) -> None:
        self.put("toy.dat")
        output = self.root / "manifest.json"
        result, report = self.scan("--output", output)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)

    def test_empty_tree_is_incomplete_without_candidates(self) -> None:
        result, report = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertFalse(report["files"])

    def test_missing_root_does_not_echo_absolute_path(self) -> None:
        result, report = self.scan(source=self.root / "missing-personal-root")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertTrue(report["errors"])

    def test_file_symlink_is_not_followed(self) -> None:
        target = self.root / "outside.dat"
        target.write_bytes(b"unselected-outside-bytes")
        link = self.source / "linked.dat"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"File symlinks unavailable: {type(error).__name__}")
        result, report = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertFalse(any(row["path"] == "linked.dat" for row in report["files"]))

    def test_directory_symlink_is_not_traversed(self) -> None:
        target = self.root / "outside"
        self.put("outside.dat", b"unselected", root=target)
        link = self.source / "linked"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Directory symlinks unavailable: {type(error).__name__}")
        result, report = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertFalse(report["files"])

    @unittest.skipUnless(os.name == "nt", "Windows reparse-point/junction behavior")
    def test_windows_junction_is_not_traversed(self) -> None:
        target = self.root / "outside"
        self.put("outside.dat", b"unselected", root=target)
        link = self.source / "junction"
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        created = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
                                 capture_output=True, text=True, timeout=20)
        if created.returncode:
            self.skipTest("Creating a Windows junction is unavailable")
        try:
            result, report = self.scan()
            self.assertEqual(result.returncode, 1)
            self.assertFalse(report["complete"])
            self.assertFalse(report["files"])
            self.assertEqual((target / "outside.dat").read_bytes(), b"unselected")
        finally:
            info = link.lstat()
            self.assertTrue(getattr(info, "st_file_attributes", 0) & 0x400)
            link.rmdir()  # Remove only the synthetic junction, never recurse into target.

    @unittest.skipIf(os.name == "nt", "Case-sensitive filename fixture")
    def test_case_colliding_paths_make_manifest_incomplete(self) -> None:
        self.put("Case.ltx", b"one")
        self.put("case.ltx", b"two")
        result, report = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_mo2_native_priority_base_overwrite_and_conflicts(self) -> None:
        mods, modlist, base, overwrite = self.mo2(overwrite=True)
        before = self.snapshot(self.root)
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist,
                                       "--base-dir", base, "--overwrite-dir", overwrite)
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["providers"], ["overwrite", "mod:High Toy", "mod:Low Toy", "base"])
        rows = {row["path"]: row for row in report["files"]}
        self.assertEqual(rows["gamedata/configs/shared.ltx"]["provider"], "overwrite")
        self.assertEqual(rows["gamedata/configs/shared.ltx"]["sha256"], hashlib.sha256(b"overwrite").hexdigest())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows["gamedata/configs/base.ltx"]["provider"], "base")
        conflict = report["file_conflicts"][0]
        self.assertEqual(conflict["providers"], report["providers"])
        self.assertEqual(conflict["winner"], "overwrite")
        self.assertEqual(before, self.snapshot(self.root))

    def test_mo2_top_enabled_mod_wins_without_overwrite(self) -> None:
        mods, modlist, base, _ = self.mo2()
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist, "--base-dir", base)
        self.assertEqual(result.returncode, 0)
        row = next(row for row in report["files"] if row["path"].endswith("shared.ltx"))
        self.assertEqual(row["provider"], "mod:High Toy")
        self.assertEqual(row["sha256"], hashlib.sha256(b"high").hexdigest())
        self.assertFalse(any("disabled" in row["path"] or "meta.ini" in row["path"] or
                             "mohidden" in row["path"] for row in report["files"]))

    def test_missing_enabled_provider_is_incomplete(self) -> None:
        mods, modlist, _, _ = self.mo2(missing=True)
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_mo2_separator_rows_do_not_require_provider_directories(self) -> None:
        mods, modlist, _, _ = self.mo2()
        modlist.write_text("+Example_separator\n+High Toy\n-Disabled Toy\n+Other_SEPARATOR\n", encoding="utf-8")
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["providers"], ["mod:High Toy"])
        self.assertEqual(len(report["files"]), 1)

    def test_mo2_hidden_directory_is_not_traversed(self) -> None:
        mods, modlist, _, _ = self.mo2()
        self.put("High Toy/gamedata/private.mohidden/private.ltx", b"hidden marker", root=mods)
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any("mohidden" in row["path"] for row in report["files"]))
        self.assertNotIn("hidden marker", result.stdout)

    def test_mo2_no_enabled_mods_can_inventory_explicit_base_and_overwrite(self) -> None:
        mods, modlist, base, overwrite = self.mo2(overwrite=True)
        modlist.write_text("# no enabled providers\n-High Toy\n", encoding="utf-8")
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist,
                                       "--base-dir", base, "--overwrite-dir", overwrite)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["providers"], ["overwrite", "base"])
        compared, difference = self.diff(report, report)
        self.assertEqual(compared.returncode, 0, difference)

    def test_mo2_virtual_file_and_directory_collision_is_incomplete(self) -> None:
        mods, modlist, _, _ = self.mo2()
        self.put("High Toy/ambiguous", b"file", root=mods)
        self.put("Low Toy/ambiguous/nested.ltx", b"nested", root=mods)
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_overlapping_mo2_roots_are_rejected(self) -> None:
        mods, modlist, _, _ = self.mo2()
        result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist, "--base-dir", mods)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_foreign_unsafe_and_duplicate_modlists_are_rejected(self) -> None:
        mods, modlist, _, _ = self.mo2()
        for text in ("*High Toy\n", "+../outside\n", "+High Toy\n+high toy\n", "+C:drive\n"):
            with self.subTest(text=text):
                modlist.write_text(text, encoding="utf-8")
                result, report = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["complete"])

    def test_identical_diff_is_complete_with_exit_zero(self) -> None:
        manifest = self.valid_manifest()
        result, report = self.diff(manifest, manifest)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["complete"])
        self.assertEqual(report["summary"]["identical_files"], 1)
        for field in ("added", "removed", "changed", "provider_changes"):
            self.assertEqual(report[field], [])

    def test_diff_detects_same_length_changes_missing_and_additional_files(self) -> None:
        self.put("shared.ltx", b"old")
        self.put("removed.ltx", b"gone")
        self.put("unchanged.script", b"same")
        _, baseline = self.scan()
        (self.source / "shared.ltx").write_bytes(b"new")
        (self.source / "removed.ltx").unlink()
        self.put("added.ltx", b"fresh")
        _, candidate = self.scan()
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report["complete"])
        self.assertEqual([row["path"] for row in report["added"]], ["added.ltx"])
        self.assertEqual([row["path"] for row in report["removed"]], ["removed.ltx"])
        self.assertEqual([row["path"] for row in report["changed"]], ["shared.ltx"])
        self.assertEqual(report["summary"]["identical_files"], 1)
        self.assertFalse(report["provider_changes"])

    def test_case_only_path_spelling_change_is_not_a_content_difference(self) -> None:
        baseline = self.valid_manifest()
        candidate = copy.deepcopy(baseline)
        candidate["files"][0]["path"] = candidate["files"][0]["path"].upper()
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["complete"])

    def test_identical_content_different_provider_is_separate_finding(self) -> None:
        mods, modlist, _, _ = self.mo2()
        (mods / "Low Toy/gamedata/configs/shared.ltx").write_bytes(b"high")
        _, baseline = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        modlist.write_text("+Low Toy\n+High Toy\n", encoding="utf-8")
        _, candidate = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(report["changed"])
        self.assertEqual([row["path"] for row in report["provider_changes"]], ["gamedata/configs/shared.ltx"])
        change = report["provider_changes"][0]
        self.assertEqual(change["baseline"]["provider"], "mod:High Toy")
        self.assertEqual(change["candidate"]["provider"], "mod:Low Toy")

    def test_different_limits_do_not_make_equivalent_selection_incomparable(self) -> None:
        manifest = self.valid_manifest()
        _, candidate = self.scan("--max-file-bytes", 1000)
        result, report = self.diff(manifest, candidate)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["complete"])

    def test_filter_policy_mismatch_is_rejected(self) -> None:
        manifest = self.valid_manifest()
        _, candidate = self.scan("--extensions", ".ltx")
        result, report = self.diff(manifest, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_manifest_mode_mismatch_is_rejected(self) -> None:
        manifest = self.valid_manifest()
        mods, modlist, _, _ = self.mo2()
        _, candidate = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        result, report = self.diff(manifest, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_incomplete_manifest_cannot_be_compared(self) -> None:
        manifest = self.valid_manifest()
        candidate = copy.deepcopy(manifest)
        candidate["complete"] = False
        result, report = self.diff(manifest, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_strict_manifest_schema_and_types(self) -> None:
        baseline = self.valid_manifest()
        mutations = [
            lambda value: value.update(schema_version=True),
            lambda value: value.update(schema_version=999),
            lambda value: value.update(kind="unrecognized"),
            lambda value: value.update(hash_algorithm="md5"),
            lambda value: value.update(unknown_field="private injected text"),
            lambda value: value["files"][0].update(bytes=True),
            lambda value: value["files"][0].update(bytes=-1),
            lambda value: value["files"][0].update(sha256="g" * 64),
            lambda value: value["files"][0].update(sha256="a" * 63),
            lambda value: value["files"][0].update(provider="mod:Not Declared"),
            lambda value: value["summary"].update(files=42),
            lambda value: value["summary"].update(bytes=42),
            lambda value: value["selection"].update(excluded_files=[]),
        ]
        for number, mutate in enumerate(mutations):
            with self.subTest(mutation=number):
                candidate = copy.deepcopy(baseline)
                mutate(candidate)
                result, report = self.diff(baseline, candidate)
                self.assertEqual(result.returncode, 1, report)
                self.assertFalse(report["complete"])
                self.assertNotIn("private injected text", result.stdout)

    def test_unsafe_manifest_paths_and_case_duplicates_are_rejected(self) -> None:
        baseline = self.valid_manifest()
        for path in ("../outside.ltx", "/absolute.ltx", "C:/absolute.ltx", "a\\b.ltx", "a//b.ltx", "a/./b.ltx", "CON", "a/b."):
            with self.subTest(path=path):
                candidate = copy.deepcopy(baseline)
                candidate["files"][0]["path"] = path
                result, report = self.diff(baseline, candidate)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["complete"])
        candidate = copy.deepcopy(baseline)
        duplicate = copy.deepcopy(candidate["files"][0])
        duplicate["path"] = duplicate["path"].upper()
        candidate["files"].append(duplicate)
        candidate["summary"]["files"] += 1
        candidate["summary"]["bytes"] *= 2
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_malformed_and_duplicate_key_json_are_rejected(self) -> None:
        baseline = self.valid_manifest()
        left = self.save("baseline.json", baseline)
        right = self.root / "malformed.json"
        for text in ("{", json.dumps(baseline) + " {}", '{"schema_version": 1, "schema_version": 1}',
                     json.dumps(baseline).replace('"schema_version": 1', '"schema_version": NaN')):
            with self.subTest(text=text[:30]):
                right.write_text(text, encoding="utf-8")
                result, report = self.run_tool("diff", "--baseline", left, "--candidate", right)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["complete"])

    def test_invalid_conflict_references_are_rejected(self) -> None:
        mods, modlist, _, _ = self.mo2()
        _, baseline = self.run_tool("scan", "--mods-dir", mods, "--modlist", modlist)
        candidate = copy.deepcopy(baseline)
        candidate["file_conflicts"][0]["winner"] = "mod:Low Toy"
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_oversized_and_excessively_nested_manifests_fail_cleanly(self) -> None:
        baseline = self.valid_manifest()
        left = self.save("baseline.json", baseline)
        right = self.root / "invalid-size-or-depth.json"
        with right.open("wb") as stream:
            stream.truncate(32 * 1024 * 1024 + 1)
        result, report = self.run_tool("diff", "--baseline", left, "--candidate", right)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        right.write_text("[" * 1500 + "0" + "]" * 1500, encoding="utf-8")
        result, report = self.run_tool("diff", "--baseline", left, "--candidate", right)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_diff_cannot_replace_an_input_manifest(self) -> None:
        manifest = self.valid_manifest()
        left = self.save("baseline.json", manifest)
        right = self.save("candidate.json", manifest)
        before = left.read_bytes()
        result, report = self.run_tool("diff", "--baseline", left, "--candidate", right, "--output", left)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])
        self.assertEqual(left.read_bytes(), before)

    def test_manifest_path_depth_above_128_components_is_rejected(self) -> None:
        baseline = self.valid_manifest()
        candidate = copy.deepcopy(baseline)
        candidate["files"][0]["path"] = "/".join(["a"] * 128 + ["toy.ltx"])
        result, report = self.diff(baseline, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["complete"])

    def test_generated_example_and_refusal_to_overwrite(self) -> None:
        destination = self.root / "demo"
        result = subprocess.run([sys.executable, "-B", str(EXAMPLE), "--destination", str(destination)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        _, baseline = self.scan(source=destination / "baseline")
        _, candidate = self.scan(source=destination / "candidate")
        diff, report = self.diff(baseline, candidate)
        self.assertEqual(diff.returncode, 2)
        self.assertEqual(report["summary"]["added"], 1)
        self.assertEqual(report["summary"]["removed"], 1)
        self.assertEqual(report["summary"]["changed"], 1)
        before = self.snapshot(destination)
        again = subprocess.run([sys.executable, "-B", str(EXAMPLE), "--destination", str(destination)],
                               capture_output=True, text=True, timeout=20)
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(before, self.snapshot(destination))


if __name__ == "__main__":
    unittest.main()
