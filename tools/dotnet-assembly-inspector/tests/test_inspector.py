# SPDX-License-Identifier: MIT
"""Dependency-free integration tests. Requires Python 3.12+ and the .NET 9 SDK.

Builds only this tool and self-authored fixtures into a temporary directory.
Never runs or loads the inspected fixture DLL.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("dotnet") is None:
            raise RuntimeError("The .NET 9 SDK is required to run these tests.")
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="outlands-assembly-tests-", dir=os.environ.get("OUTLANDS_TEST_TEMP")
        )
        cls.scratch = Path(cls.temporary.name)
        cls.artifacts = cls.scratch / "artifacts"
        cls.environment = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1")
        cls.sentinel = cls.scratch / "fixture-executed.txt"
        cls.environment["OUTLANDS_INSPECTOR_FIXTURE_SENTINEL"] = str(cls.sentinel)
        for project in (ROOT / "Inspector.csproj", ROOT / "tests/fixtures/Fixture.csproj"):
            result = subprocess.run(
                ["dotnet", "build", str(project), "--configuration", "Release", "--nologo",
                 "--artifacts-path", str(cls.artifacts), "-v", "quiet"],
                capture_output=True, text=True, timeout=120, env=cls.environment,
            )
            if result.returncode:
                raise RuntimeError(f"Synthetic build failed:\n{result.stdout}\n{result.stderr}")
        cls.tool = next((cls.artifacts / "bin/Inspector").glob("**/Outlands.AssemblyInspector.dll"))
        cls.fixture = next((cls.artifacts / "bin/Fixture").glob("**/Outlands.SyntheticFixture.dll"))
        cls.before = hashlib.sha256(cls.fixture.read_bytes()).hexdigest()
        result = cls.invoke(cls.fixture)
        if result.returncode:
            raise RuntimeError(f"Synthetic inspection failed: {result.stderr}")
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, "fixture"):
                if hashlib.sha256(cls.fixture.read_bytes()).hexdigest() != cls.before:
                    raise AssertionError("Inspected fixture changed.")
                if cls.sentinel.exists():
                    raise AssertionError("Inspected fixture code executed.")
        finally:
            cls.temporary.cleanup()

    @classmethod
    def invoke(cls, *arguments):
        return subprocess.run(
            ["dotnet", str(cls.tool), *(str(arg) for arg in arguments)],
            capture_output=True, text=True, timeout=30, env=cls.environment,
        )

    def failed(self, *arguments):
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "", "Incomplete JSON must not be published.")
        self.assertTrue(result.stderr.strip())
        return result

    def test_identity_and_schema(self):
        self.assertEqual(self.report["schemaVersion"], "1.0")
        self.assertEqual(self.report["assembly"]["name"], "Outlands.SyntheticFixture")
        self.assertEqual(self.report["inspection"], "static-managed-metadata")
        self.assertEqual(self.report["module"]["name"], "Outlands.SyntheticFixture.dll")

    def test_types_and_interface_tokens(self):
        example = next(item for item in self.report["types"] if item["name"] == "Example")
        self.assertEqual(example["ns"], "Outlands.Synthetic")
        self.assertRegex(example["token"], r"^02[0-9A-F]{6}$")
        self.assertTrue(example["interfaces"])

    def test_fields_and_explicit_layout(self):
        positioned = next(item for item in self.report["fields"] if item["name"] == "Number")
        self.assertEqual(positioned["offset"], 4)
        constant = next(item for item in self.report["fields"] if item["name"] == "Meaning")
        self.assertTrue(constant["constant"].startswith("0B"))

    def test_il_and_bodyless_method(self):
        echo = next(item for item in self.report["methods"] if item["name"] == "Echo" and item["il"])
        self.assertRegex(echo["il"], r"^(?:[0-9A-F]{2})+$")
        no_body = next(item for item in self.report["methods"] if item["name"] == "NoBody")
        self.assertEqual(no_body["il"], "")
        self.assertIsNone(no_body["maxStack"])

    def test_exception_regions_are_retained(self):
        handle = next(item for item in self.report["methods"] if item["name"] == "Handle")
        kinds = {item["kind"] for item in handle["exceptions"]}
        self.assertIn("Filter", kinds)
        self.assertIn("Finally", kinds)
        for region in handle["exceptions"]:
            if region["kind"] != "Filter":
                self.assertIsNone(region["filterOffset"])

    def test_unicode_and_escaped_user_strings(self):
        strings = [item["value"] for item in self.report["userStrings"]]
        self.assertIn('synthetic fixture: quotation " newline\nUnicode Ω', strings)

    def test_references_attributes_and_debug(self):
        self.assertTrue(self.report["refs"])
        self.assertTrue(self.report["memberRefs"])
        self.assertTrue(self.report["attrs"])
        self.assertTrue(self.report["debug"])

    def test_inspection_does_not_execute_module_initializer(self):
        self.assertFalse(self.sentinel.exists())

    def test_input_is_unchanged(self):
        self.assertEqual(hashlib.sha256(self.fixture.read_bytes()).hexdigest(), self.before)

    def test_no_input_path_export(self):
        report = json.dumps(self.report)
        self.assertNotIn(str(self.scratch), report)
        self.assertNotIn(str(ROOT), report)

    def test_cli_help_and_version(self):
        self.assertEqual(self.invoke("--help").returncode, 0)
        self.assertIn("1.0.0", self.invoke("--version").stdout)

    def test_cli_errors(self):
        self.failed()
        self.failed("--unknown")
        self.failed(self.fixture, "extra")

    def test_missing_file_error_does_not_echo_private_path(self):
        missing = self.scratch / "private-path-marker.dll"
        result = self.failed(missing)
        self.assertNotIn(str(missing), result.stderr)
        self.assertNotIn("private-path-marker", result.stderr)

    def test_empty_and_truncated_inputs(self):
        for label, data in (("empty", b""), ("truncated", self.fixture.read_bytes()[:256]),
                            ("text", b"this is self-authored synthetic text")):
            path = self.scratch / (label + ".dll")
            path.write_bytes(data)
            self.failed(path)

    def test_native_like_pe_without_managed_metadata(self):
        data = bytearray(512)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3C, 0x80)
        data[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HHIIIHH", data, 0x84, 0x14C, 0, 0, 0, 0, 224, 0x102)
        struct.pack_into("<H", data, 0x98, 0x10B)
        struct.pack_into("<I", data, 0x98 + 92, 16)
        path = self.scratch / "synthetic-native.dll"
        path.write_bytes(data)
        self.failed(path)

    def test_oversized_input_has_no_json(self):
        path = self.scratch / "oversized.dll"
        with path.open("wb") as stream:
            stream.truncate(32 * 1024 * 1024 + 1)
        self.failed(path)

    def test_malformed_user_string_is_not_silently_skipped(self):
        data = bytearray(self.fixture.read_bytes())
        metadata_root = data.index(b"BSJB")
        stream_name = data.index(b"#US\0", metadata_root)
        offset, size = struct.unpack_from("<II", data, stream_name - 8)
        self.assertGreater(size, 8)
        data[metadata_root + offset + 1] = 0xFF  # Invalid compressed length prefix.
        path = self.scratch / "malformed-user-strings.dll"
        path.write_bytes(data)
        self.failed(path)

    def build_literals(self, name, literals):
        source = self.scratch / name
        source.mkdir()
        (source / (name + ".csproj")).write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
            '<TargetFramework>net9.0</TargetFramework>'
            '</PropertyGroup></Project>', encoding="utf-8"
        )
        methods = [f'public static string M{index}() => "{literal}";'
                   for index, literal in enumerate(literals)]
        (source / "Literals.cs").write_text(
            "public static class SyntheticLiterals {" + "".join(methods) + "}",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["dotnet", "build", str(source / (name + ".csproj")),
             "--configuration", "Release", "--nologo", "--artifacts-path", str(self.artifacts),
             "-v", "quiet"], capture_output=True, text=True, timeout=120, env=self.environment,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return next((self.artifacts / "bin" / name).glob("**/" + name + ".dll"))

    def test_well_formed_oversized_decoded_value_is_rejected(self):
        fixture = self.build_literals("LargeValue", ["x" * 600_000])
        self.assertLess(fixture.stat().st_size, 32 * 1024 * 1024)
        self.failed(fixture)

    def test_json_expansion_limit_emits_no_partial_report(self):
        # Each string fits the individual decoded bound; ten strings use about
        # 6 MiB decoded storage but JSON's \u0001 escaping expands past 16 MiB.
        fixture = self.build_literals(
            "EscapedValues", [str(index) + r"\u0001" * 300_000 for index in range(10)]
        )
        self.assertLess(fixture.stat().st_size, 32 * 1024 * 1024)
        self.failed(fixture)


if __name__ == "__main__":
    unittest.main(verbosity=2)
