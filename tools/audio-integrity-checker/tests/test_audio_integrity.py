"""Black-box checks using generated audio and disposable MO2 trees only.

No installed game, mod audio, playback device, or network service is used.  The
native decoder dependency is mandatory: a missing decoder fails test setup
instead of silently turning the important tests into skips.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave


SCRIPT = Path(__file__).resolve().parents[1] / "audio_integrity.py"
EXAMPLE = SCRIPT.parent / "examples" / "create_example.py"


def wav_bytes(*, channels=1, sample_rate=44100, frames=64):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        # Every channel is generated locally; no recording or game asset.
        samples = [((index % 17) - 8) * 500
                   for index in range(frames * channels)]
        output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return target.getvalue()


class FixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="audio-integrity-tests-")
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

    def file(self, relative, contents=None, root=None):
        target = (root or self.source) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(wav_bytes() if contents is None else contents)
        return target

    def invoke(self, *extra, mo2=False, no_site=False, timeout=30):
        arguments = (["--mods-dir", str(self.mods), "--modlist", str(self.modlist)]
                     if mo2 else ["--source-dir", str(self.source)])
        environment = dict(os.environ)
        if no_site:
            environment.pop("PYTHONPATH", None)
        return subprocess.run(
            [sys.executable, "-B", *(["-S"] if no_site else []), str(SCRIPT),
             *arguments, *map(str, extra)],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            timeout=timeout,
        )

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
        self.assertNotIn("Traceback", public_text)
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
    def test_help_and_version_work_without_decoder(self):
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
                for name in ("--source-dir", "--mods-dir", "--modlist", "--output",
                             "--max-file-bytes", "--max-frames", "--sha256"):
                    self.assertIn(name, process.stdout)

    def test_missing_dependency_is_incomplete_without_fake_pass(self):
        self.file("safe.wav")
        report = self.check_report(self.invoke(no_site=True), 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_files"], 0)
        self.assertEqual(report["summary"]["passes"], 0)
        self.assertTrue(report["errors"])
        self.assertFalse(any(item["status"] == "DECODE_PASS" for item in report["files"]))


class AudioCheckerCliTests(FixtureTests):
    @classmethod
    def setUpClass(cls):
        # This is a required native-codec preflight, not SkipTest.  Tested wheels
        # must actually provide OGG/Vorbis and FLAC as well as uncompressed WAV.
        import numpy as np
        import soundfile as sf
        cls.np, cls.sf = np, sf
        if sf.__version__ != "0.13.1" or np.__version__ != "2.2.6":
            raise RuntimeError("Install the reviewed SoundFile 0.13.1 and NumPy 2.2.6 dependencies")
        for format_name, subtype in (("OGG", "VORBIS"), ("FLAC", "PCM_16"),
                                     ("WAV", "FLOAT")):
            if not sf.check_format(format_name, subtype):
                raise RuntimeError(f"The tested native decoder lacks {format_name}/{subtype}")

    def test_mono_stereo_and_ordinary_sample_rates_are_not_corruption(self):
        for channels in (1, 2):
            for rate in (32000, 44100, 48000):
                self.file(f"pcm-{channels}-{rate}.wav",
                          wav_bytes(channels=channels, sample_rate=rate))
        self.file("ignored.txt", b"this is deliberately not audio")
        report = self.inspect()
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_files"], 6)
        self.assertEqual(report["summary"]["passes"], 6)
        self.assertEqual({item["status"] for item in report["files"]}, {"DECODE_PASS"})
        self.assertEqual({item["channels"] for item in report["files"]}, {1, 2})
        self.assertEqual({item["sample_rate"] for item in report["files"]},
                         {32000, 44100, 48000})
        self.assertTrue(all(item["decoded_frames"] == 64 for item in report["files"]))

    def test_generated_ogg_flac_and_aiff_decode_with_actual_native_codecs(self):
        samples = self.np.linspace(-0.5, 0.5, 256, dtype="float32")
        for extension, format_name, subtype in (("ogg", "OGG", "VORBIS"),
                                                ("flac", "FLAC", "PCM_16"),
                                                ("aiff", "AIFF", "PCM_16"),
                                                ("aif", "AIFF", "PCM_16")):
            self.sf.write(str(self.source / f"generated.{extension}"), samples,
                          32000, format=format_name, subtype=subtype)
        report = self.inspect()
        self.assertEqual(report["summary"]["passes"], 4)
        self.assertEqual({item["format"] for item in report["files"]}, {"OGG", "FLAC", "AIFF"})
        self.assertTrue(all(item["decoded_frames"] == 256 for item in report["files"]))
        self.assertEqual(report["runtime"]["soundfile_version"], "0.13.1")
        self.assertEqual(report["runtime"]["numpy_version"], "2.2.6")
        self.assertTrue(report["runtime"]["libsndfile_version"])

    def test_empty_audio_is_a_complete_integrity_finding(self):
        self.file("empty.wav", wav_bytes(frames=0))
        report = self.inspect(status=2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["anomalies"], 1)
        item, = report["files"]
        self.assertEqual(item["status"], "DECODE_ANOMALY")
        self.assertEqual(item["decoded_frames"], 0)
        self.assertTrue(item["issues"])

    def test_invalid_ogg_is_decode_error_without_native_error_or_raw_bytes(self):
        secret = "PRIVATE_AUDIO_BYTES_784716"
        self.file("broken.ogg", secret.encode("ascii"))
        process = self.invoke()
        report = self.check_report(process, 2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["decode_errors"], 1)
        self.assertEqual(report["files"][0]["status"], "DECODE_ERROR")
        self.assertNotIn(secret, process.stdout + process.stderr)
        self.assertNotIn("LibsndfileError", process.stdout + process.stderr)
        self.assertNotIn("Error opening", process.stdout + process.stderr)

    def test_float_nan_and_infinity_are_detected_without_clipping_to_pcm(self):
        target = self.source / "nonfinite.wav"
        self.sf.write(str(target), self.np.array([0.0, self.np.nan,
                                                self.np.inf, -self.np.inf],
                                               dtype="float32"),
                      48000, format="WAV", subtype="FLOAT")
        report = self.inspect(status=2)
        self.assertTrue(report["summary"]["complete"])
        item, = report["files"]
        self.assertEqual(item["status"], "DECODE_ANOMALY")
        self.assertFalse(item["finite_samples"])
        self.assertEqual(item["decoded_frames"], 4)
        self.assertTrue(item["issues"])

    def test_truncated_pcm_report_matches_what_native_decoder_can_observe(self):
        # libsndfile can silently repair a PCM header's frame count from the
        # available bytes.  Do not claim that decoding detects every truncation.
        target = self.file("shortened.wav", wav_bytes(frames=64)[:-20])
        with self.sf.SoundFile(str(target)) as native:
            observable_frames = native.frames
            actual_frames = len(native.read(dtype="float64", always_2d=True))
        report = self.inspect(status=0 if observable_frames == actual_frames and actual_frames else 2)
        item, = report["files"]
        self.assertEqual(item["declared_frames"], observable_frames)
        self.assertEqual(item["decoded_frames"], actual_frames)
        self.assertLess(actual_frames, 64)

    def test_source_bytes_mtime_and_optional_sha256_are_unchanged(self):
        target = self.file("nested/valid.wav")
        self.file("broken.flac", b"synthetic invalid audio")
        before = self.snapshot(self.source)
        report = self.inspect("--sha256", status=2)
        item = next(item for item in report["files"] if item["path"] == "nested/valid.wav")
        self.assertEqual(item["sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual(self.snapshot(self.source), before)

    def test_default_report_has_no_hash_and_is_deterministic(self):
        self.file("z.wav")
        self.file("a.wav")
        first = self.inspect()
        self.assertEqual(first, self.inspect())
        self.assertEqual([item["path"] for item in first["files"]], ["a.wav", "z.wav"])
        self.assertTrue(all(item["sha256"] is None for item in first["files"]))

    def test_wav_text_tags_are_not_exposed_in_report(self):
        secret = b"PRIVATE_TAG_TEXT_828826"
        # A standard RIFF LIST/INFO/INAM text tag, generated in this test.
        tag = b"INAM" + struct.pack("<I", len(secret)) + secret
        tag += b"\0" * (len(secret) % 2)
        chunk = b"LIST" + struct.pack("<I", len(tag) + 4) + b"INFO" + tag
        contents = bytearray(wav_bytes() + chunk)
        struct.pack_into("<I", contents, 4, len(contents) - 8)
        self.file("tagged.wav", bytes(contents))
        process = self.invoke()
        self.check_report(process)
        self.assertNotIn(secret.decode("ascii"), process.stdout + process.stderr)
        self.assertNotIn("INAM", process.stdout + process.stderr)

    def test_empty_candidate_set_is_incomplete(self):
        self.file("ignored.txt", b"no audio here")
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["effective_files"], 0)
        self.assertEqual(report["summary"]["passes"], 0)

    def test_file_size_limit_skip_is_incomplete_and_boundary_is_inclusive(self):
        target = self.file("size.wav")
        size = target.stat().st_size
        report = self.inspect("--max-file-bytes", size - 1, status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["checked_files"], 0)
        self.assertEqual(report["summary"]["skipped_files"], 1)
        self.assertEqual(report["files"][0]["status"], "SKIPPED")
        self.assertEqual(self.inspect("--max-file-bytes", size)["summary"]["passes"], 1)

    def test_decode_frame_cap_is_incomplete_and_never_reports_pass(self):
        self.file("long.wav", wav_bytes(frames=64))
        report = self.inspect("--max-frames", "63", status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 0)
        self.assertEqual(report["files"][0]["status"], "SKIPPED")
        self.assertEqual(self.inspect("--max-frames", "64")["summary"]["passes"], 1)

    def test_channel_cap_is_incomplete_and_boundary_is_inclusive(self):
        self.file("stereo.wav", wav_bytes(channels=2))
        report = self.inspect("--max-channels", "1", status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 0)
        self.assertEqual(self.inspect("--max-channels", "2")["summary"]["passes"], 1)

    def test_invalid_limits_fail_without_traceback_or_private_paths(self):
        self.file("valid.wav")
        for option in ("--max-file-bytes", "--max-frames", "--max-channels"):
            for value in ("0", "-1", str(10 ** 100)):
                with self.subTest(option=option, value=value):
                    process = self.invoke(option, value)
                    self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                    text = process.stdout + process.stderr
                    self.assertNotIn("Traceback", text)
                    self.assertNotIn(str(self.base), text)

    def test_mo2_inspects_only_highest_priority_effective_audio(self):
        self.file("sounds/shared.wav", root=self.mods / "High")
        self.file("sounds/shared.wav", b"invalid shadowed audio", self.mods / "Low")
        report = self.inspect(mo2=True)
        self.assertEqual(report["summary"]["loose_audio_files"], 2)
        self.assertEqual(report["summary"]["effective_files"], 1)
        self.assertEqual(report["summary"]["shadowed_files"], 1)
        self.assertEqual(report["summary"]["passes"], 1)
        item, = report["files"]
        self.assertEqual(item["provider"], "High")
        conflict, = report["file_conflicts"]
        self.assertEqual(conflict["winner"]["name"], "High")
        self.assertEqual([provider["name"] for provider in conflict["providers_in_priority_order"]],
                         ["High", "Low"])

    def test_high_priority_decode_error_is_not_hidden_by_valid_lower_mod(self):
        self.file("same.wav", b"invalid winner", self.mods / "High")
        self.file("same.wav", root=self.mods / "Low")
        report = self.inspect(mo2=True, status=2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["decode_errors"], 1)
        self.assertEqual(report["files"][0]["provider"], "High")

    def test_base_and_overwrite_priority_preserves_every_input(self):
        base = self.base / "base synthetic"
        overwrite = self.base / "overwrite synthetic"
        base.mkdir()
        overwrite.mkdir()
        self.file("same.wav", b"invalid base audio", base)
        self.file("same.wav", b"invalid mod audio", self.mods / "High")
        self.file("same.wav", root=overwrite)
        self.file("base-only.wav", root=base)
        self.file("mod-only.wav", root=self.mods / "Low")
        before = self.snapshot(base, self.mods, self.modlist, overwrite)
        report = self.inspect("--base-dir", base, "--overwrite-dir", overwrite, mo2=True)
        self.assertEqual(report["summary"]["passes"], 3)
        item = next(item for item in report["files"] if item["path"] == "same.wav")
        self.assertEqual(item["kind"], "overwrite")
        conflict, = report["file_conflicts"]
        self.assertEqual([provider["kind"] for provider in conflict["providers_in_priority_order"]],
                         ["overwrite", "mod", "base"])
        self.assertEqual(self.snapshot(base, self.mods, self.modlist, overwrite), before)

    def test_disabled_separator_and_mohidden_audio_are_not_inspected(self):
        self.modlist.write_text("-Disabled\n+Group_separator\n+High\n", encoding="utf-8")
        self.file("bad.wav", b"invalid", self.mods / "Disabled")
        self.file("valid.wav", root=self.mods / "High")
        self.file("bad.wav.mohidden", b"invalid", self.mods / "High")
        self.file("folder.mohidden/bad.wav", b"invalid", self.mods / "High")
        report = self.inspect(mo2=True)
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual([item["path"] for item in report["files"]], ["valid.wav"])

    def test_missing_enabled_mod_takes_precedence_over_complete_decode_findings(self):
        self.modlist.write_text("+Missing\n+High\n", encoding="utf-8")
        self.file("bad.ogg", b"synthetic invalid", self.mods / "High")
        report = self.inspect(mo2=True, status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["decode_errors"], 1)

    def test_foreign_modlist_entry_never_reads_outside_mods(self):
        secret = b"PRIVATE_OUTSIDE_CONTENT_82297"
        self.file("private.ogg", secret, self.base / "outside")
        self.modlist.write_text("+../outside\n+High\n", encoding="utf-8")
        self.file("valid.wav", root=self.mods / "High")
        process = self.invoke(mo2=True)
        report = self.check_report(process, 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual(report["summary"]["decode_errors"], 0)
        self.assertNotIn(secret.decode("ascii"), process.stdout + process.stderr)

    def test_conflict_keys_follow_windows_case_insensitive_relative_paths(self):
        self.file("SOUNDS/Shared.WAV", root=self.mods / "High")
        self.file("sounds/shared.wav", b"invalid shadowed", self.mods / "Low")
        report = self.inspect(mo2=True)
        self.assertEqual(report["summary"]["effective_files"], 1)
        self.assertEqual(report["files"][0]["path"], "sounds/shared.wav")
        self.assertEqual(report["summary"]["passes"], 1)

    def test_report_is_only_created_by_explicit_new_output_option(self):
        self.file("valid.wav")
        before = self.snapshot(self.source)
        report = self.inspect()
        self.assertEqual(self.snapshot(self.source), before)
        output = self.base / "new report.json"
        self.assertFalse(output.exists())
        written = self.check_report(self.invoke("--output", output), output=output)
        self.assertEqual(report, written)
        self.assertEqual(self.snapshot(self.source), before)

    def test_existing_output_is_never_overwritten(self):
        self.file("valid.wav")
        output = self.base / "existing.json"
        output.write_text("do not replace", encoding="utf-8")
        process = self.invoke("--output", output)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "do not replace")

    def test_output_inside_source_or_mo2_inputs_is_rejected(self):
        self.file("valid.wav")
        self.file("valid.wav", root=self.mods / "High")
        for root, mo2 in ((self.source, False), (self.mods / "High", True)):
            with self.subTest(root=root):
                output = root / "must-not-write.json"
                process = self.invoke("--output", output, mo2=mo2)
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                self.assertFalse(output.exists())

    def test_output_cannot_replace_modlist_but_new_sibling_report_is_allowed(self):
        self.file("valid.wav", root=self.mods / "High")
        before = self.modlist.read_bytes()
        process = self.invoke("--output", self.modlist, mo2=True)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(self.modlist.read_bytes(), before)
        output = self.modlist.parent / "new-report.json"
        report = self.check_report(self.invoke("--output", output, mo2=True), output=output)
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual(self.modlist.read_bytes(), before)

    def test_output_inside_base_and_overwrite_sources_is_rejected(self):
        base = self.base / "base"
        overwrite = self.base / "overwrite"
        self.file("valid.wav", root=base)
        self.file("valid.wav", root=overwrite)
        for root in (base, overwrite):
            with self.subTest(root=root):
                output = root / "must-not-write.json"
                process = self.invoke("--base-dir", base, "--overwrite-dir", overwrite,
                                      "--output", output, mo2=True)
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                self.assertFalse(output.exists())

    def test_output_device_and_alternate_stream_spellings_are_rejected(self):
        self.file("valid.wav")
        before = self.snapshot(self.base)
        for name in ("NUL", "CON.json", "COM1", "output.json:secret"):
            with self.subTest(name=name):
                output = self.base / name
                process = self.invoke("--output", output)
                self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                # Windows reports its NUL device as existing even when no
                # directory entry was created.  Compare the actual fixture.
                self.assertEqual(self.snapshot(self.base), before)

    def test_output_parent_must_already_exist(self):
        self.file("valid.wav")
        output = self.base / "not-created" / "report.json"
        process = self.invoke("--output", output)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertFalse(output.parent.exists())

    def test_overlapping_input_roots_are_rejected(self):
        self.file("valid.wav", root=self.mods / "High")
        for option, root in (("--base-dir", self.mods),
                             ("--overwrite-dir", self.mods / "High")):
            with self.subTest(option=option):
                report = self.inspect(option, root, mo2=True, status=1)
                self.assertFalse(report["summary"]["complete"])

    def test_invalid_cli_mode_is_rejected_without_traceback(self):
        process = self.invoke("--mods-dir", self.mods, "--modlist", self.modlist)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertNotIn("Traceback", process.stdout + process.stderr)
        self.assertNotIn(str(self.base), process.stdout + process.stderr)

    def test_directory_link_is_not_followed(self):
        outside = self.base / "outside"
        self.file("secret.wav", root=outside)
        self.file("valid.wav")
        link = self.source / "outside-link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt":
                self.skipTest("Directory symbolic links are unavailable")
            environment = dict(os.environ, AUDIO_TEST_JUNCTION=str(link),
                               AUDIO_TEST_TARGET=str(outside))
            process = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "New-Item -ItemType Junction -Path $env:AUDIO_TEST_JUNCTION "
                 "-Target $env:AUDIO_TEST_TARGET -ErrorAction Stop | Out-Null"],
                env=environment, capture_output=True, text=True, timeout=20,
            )
            if process.returncode:
                self.skipTest("This Windows account cannot create a disposable directory link")
        # Remove only the link itself, inside the verified disposable fixture;
        # never use recursive deletion or traverse its target for cleanup.
        def remove_link():
            fixture_root = self.base.resolve(strict=True)
            self.assertTrue(link.parent.resolve(strict=True).is_relative_to(fixture_root))
            self.assertTrue(outside.resolve(strict=True).is_relative_to(fixture_root))
            self.assertEqual(link.parent.resolve(), self.source.resolve())
            self.assertEqual(link.resolve(strict=True), outside.resolve(strict=True))
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                self.assertTrue(link.is_junction())
                link.rmdir()
            self.assertFalse(link.exists())
            self.assertTrue((outside / "secret.wav").is_file())
        self.addCleanup(remove_link)
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual([item["path"] for item in report["files"]], ["valid.wav"])

    def test_file_symlink_is_not_followed_if_supported(self):
        outside = self.file("secret.wav", root=self.base / "outside")
        self.file("valid.wav")
        link = self.source / "linked.wav"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("This account cannot create file symbolic links")
        self.addCleanup(link.unlink)
        report = self.inspect(status=1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertNotIn("linked.wav", [item["path"] for item in report["files"]])

    def test_example_generator_produces_source_findings_and_effective_mo2_pass(self):
        destination = self.base / "generated example"
        process = subprocess.run(
            [sys.executable, "-B", str(EXAMPLE), "--destination", str(destination)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.source = destination / "source"
        report = self.inspect(status=2)
        self.assertTrue(report["summary"]["complete"])
        self.assertEqual(report["summary"]["passes"], 1)
        self.assertEqual(report["summary"]["decode_errors"], 1)
        self.assertEqual(report["summary"]["anomalies"], 1)
        self.mods = destination / "mo2" / "mods"
        self.modlist = destination / "mo2" / "profile" / "modlist.txt"
        report = self.inspect("--base-dir", destination / "mo2" / "base",
                              "--overwrite-dir", destination / "mo2" / "overwrite", mo2=True)
        self.assertEqual(report["summary"]["passes"], 2)
        self.assertEqual(report["summary"]["shadowed_files"], 2)
        shared = next(item for item in report["files"] if item["path"] == "shared.wav")
        self.assertEqual(shared["kind"], "overwrite")
        # Re-running must refuse the existing destination, keeping the example
        # and any user edits intact.
        before = self.snapshot(destination)
        process = subprocess.run(
            [sys.executable, "-B", str(EXAMPLE), "--destination", str(destination)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.snapshot(destination), before)


if __name__ == "__main__":
    unittest.main()
