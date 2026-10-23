"""Independent stdlib ZIP fixtures and malformed metadata; no game content. MIT."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'zip_inspector.py'
GENERATOR = SCRIPT.parent / 'examples/create_example.py'
build_zip = runpy.run_path(str(GENERATOR))['build_zip']
spec = importlib.util.spec_from_file_location('zip_inspector', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def central(data):
    return struct.unpack_from('<I', data, len(data) - 6)[0]


def patch(data, offset, fmt, value):
    data = bytearray(data)
    struct.pack_into('<' + fmt, data, offset, value)
    return bytes(data)


def descriptor_zip(signed=True):
    class Unseekable(io.BytesIO):
        def seekable(self):
            return False
        def seek(self, *args):
            raise OSError('not seekable')
    stream = Unseekable()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('a.txt', b'Original descriptor example')
    data = stream.getvalue()
    if not signed:
        pos = data.index(b'PK\x07\x08')
        start = central(data)
        data = data[:pos] + data[pos+4:]
        data = patch(data, len(data)-6, 'I', start-4)
    return data


class ZipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zip-layout-')
        self.root = Path(self.temp.name)
        self.path = self.root / 'input.zip'
        self.path.write_bytes(build_zip([('a.txt', b'Original toy bytes')]))

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *options, archive=None):
        args = [sys.executable, '-B', str(SCRIPT), '--archive', 'toy=' + str(archive or self.path)]
        args.extend(str(value) for value in options)
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        text = result.stdout
        if not text and '--output' in args:
            path = Path(args[args.index('--output')+1])
            if path.is_file():
                text = path.read_text(encoding='utf-8')
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn(str(self.root), text + result.stderr)
        return result.returncode, json.loads(text)

    def incomplete(self, code):
        status, report = self.run_tool()
        self.assertEqual(status, 1)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['archive'])
        self.assertIn(code, [row['code'] for row in report['errors']])

    def test_stored_metadata_and_no_input_changes(self):
        before = self.path.read_bytes()
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertTrue(report['complete'])
        row = report['archive']['entries'][0]
        self.assertEqual((row['name'], row['uncompressed_bytes'], row['method']), ('a.txt', 18, 0))
        self.assertFalse(report['policy']['payload_integrity_checked'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_deflated_supported_without_decoding(self):
        self.path.write_bytes(build_zip([('a.txt', b'abc'*100)], zipfile.ZIP_DEFLATED))
        self.assertEqual(self.run_tool()[0], 0)

    def test_empty_archive(self):
        self.path.write_bytes(build_zip([]))
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertEqual(report['archive']['entries'], [])

    def test_archive_comment(self):
        self.path.write_bytes(build_zip([], comment=b'Toy comment'))
        self.assertEqual(self.run_tool()[1]['archive']['archive_comment_bytes'], 11)

    def test_signed_and_unsigned_descriptors(self):
        for signed in (True, False):
            with self.subTest(signed=signed):
                self.path.write_bytes(descriptor_zip(signed))
                self.assertEqual(self.run_tool()[0], 0)

    def test_explicit_directory(self):
        self.path.write_bytes(build_zip([('A/', b''), ('A/x.txt', b'toy'), ('other.txt', b'toy')]))
        self.assertEqual(self.run_tool()[0], 0)

    def test_wrapper_is_observation_requiring_review(self):
        self.path.write_bytes(build_zip([('Toy/a.txt', b'toy')]))
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(report['archive']['common_top_level_folder'], 'Toy')

    def test_unsafe_paths_are_reported_without_extraction(self):
        names = ['../outside.txt', '/root.txt', 'C:/bad.txt', 'a\\b.txt', 'NUL.txt',
                 'a//b.txt', 'trailing./a.txt', 'a/../b.txt', 'a:stream', './a.txt']
        data = build_zip([(name, b'toy') for name in names])
        # ZipInfo normalizes the host separator on Windows; restore the raw unsafe name.
        self.path.write_bytes(data.replace(b'a/b.txt', b'a\\b.txt'))
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertTrue(all('unsafe_path' in row['issues'] for row in report['archive']['entries']))
        self.assertEqual({p.name for p in self.root.iterdir()}, {'input.zip'})

    def test_embedded_nul_preserved_and_flagged(self):
        data = self.path.read_bytes().replace(b'a.txt', b'a\0txt')
        self.path.write_bytes(data)
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(report['archive']['entries'][0]['name'], 'a\0txt')

    def test_duplicates_case_collisions_and_prefixes(self):
        with self.assertWarns(UserWarning):
            self.path.write_bytes(build_zip([('a', b'1'), ('a', b'2'), ('A', b'3'),
                                            ('a-else', b'4'), ('a/child', b'5')]))
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        rows = report['archive']['entries']
        self.assertIn('duplicate_name', rows[1]['issues'])
        self.assertIn('case_or_normalization_collision', rows[2]['issues'])
        self.assertIn('file_directory_collision', rows[4]['issues'])

    def test_unicode_names_and_normalization(self):
        self.path.write_bytes(build_zip([('caf\u00e9', b'1'), ('cafe\u0301', b'2')]))
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertIn('case_or_normalization_collision', report['archive']['entries'][1]['issues'])

    def test_cp437_decode(self):
        self.path.write_bytes(self.path.read_bytes().replace(b'a.txt', b'\x82.txt'))
        self.assertEqual(self.run_tool()[1]['archive']['entries'][0]['name'], '\u00e9.txt')

    def test_unix_symlink_metadata_flagged(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, central(data)+38, 'I', (stat.S_IFLNK | 0o777) << 16))
        self.assertIn('link_or_special_entry', self.run_tool()[1]['archive']['entries'][0]['issues'])

    def test_encrypted_metadata_flagged(self):
        data = self.path.read_bytes()
        data = patch(data, 6, 'H', 1)
        self.path.write_bytes(patch(data, central(data)+8, 'H', 1))
        self.assertIn('encrypted_entry', self.run_tool()[1]['archive']['entries'][0]['issues'])

    def test_declared_size_ratio_flags(self):
        data = build_zip([('a', b'X'*50)], zipfile.ZIP_DEFLATED)
        data = patch(data, 22, 'I', 2*1024**3)
        self.path.write_bytes(patch(data, central(data)+24, 'I', 2*1024**3))
        issues = self.run_tool()[1]['archive']['entries'][0]['issues']
        self.assertIn('large_declared_entry', issues)
        self.assertIn('high_declared_ratio', issues)

    def test_payload_corruption_is_out_of_scope(self):
        data = bytearray(self.path.read_bytes())
        data[35] ^= 0xFF
        self.path.write_bytes(data)
        self.assertEqual(self.run_tool()[0], 0)

    def test_trailing_bytes_and_truncation(self):
        original = self.path.read_bytes()
        for data in (original+b'junk', original[:-1], b'not a zip'):
            self.path.write_bytes(data)
            self.assertEqual(self.run_tool()[0], 1)

    def test_ambiguous_end_record(self):
        fake = struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, 0, 0, 0, 0, 0)
        self.path.write_bytes(build_zip([], comment=fake))
        self.incomplete('missing_or_ambiguous_end_record')

    def test_multidisk_rejected(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, len(data)-18, 'H', 1))
        self.incomplete('unsupported_multidisk')

    def test_zip64_sentinel_rejected(self):
        data = self.path.read_bytes()
        data = patch(data, len(data)-14, 'H', 0xFFFF)
        self.path.write_bytes(patch(data, len(data)-12, 'H', 0xFFFF))
        self.incomplete('unsupported_zip64')

    def test_entry_limit_checked_before_central_parse(self):
        data = self.path.read_bytes()
        data = patch(data, len(data)-14, 'H', 10001)
        self.path.write_bytes(patch(data, len(data)-12, 'H', 10001))
        self.incomplete('entry_count_limit')

    def test_central_size_limit(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, len(data)-10, 'I', tool.CENTRAL_LIMIT+1))
        self.incomplete('central_byte_limit')

    def test_central_range_mismatch(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, len(data)-6, 'I', 0))
        self.incomplete('central_range_invalid')

    def test_invalid_central_signature(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, central(data), 'I', 0))
        self.incomplete('invalid_central_signature')

    def test_local_name_mismatch(self):
        data = bytearray(self.path.read_bytes())
        data[30] = ord('b')
        self.path.write_bytes(data)
        self.incomplete('local_central_mismatch')

    def test_local_size_mismatch(self):
        self.path.write_bytes(patch(self.path.read_bytes(), 18, 'I', 999))
        self.incomplete('local_central_mismatch')

    def test_local_pointer_into_central(self):
        data = self.path.read_bytes()
        self.path.write_bytes(patch(data, central(data)+42, 'I', central(data)))
        self.incomplete('local_range_invalid')

    def test_unsupported_flags_and_method(self):
        for offset, value in ((8, 0x40), (10, 99)):
            data = self.path.read_bytes()
            self.path.write_bytes(patch(data, central(data)+offset, 'H', value))
            self.incomplete('unsupported_version_method_or_flags')
            self.path.write_bytes(build_zip([('a.txt', b'Original toy bytes')]))

    def test_invalid_utf8(self):
        data = self.path.read_bytes().replace(b'a.txt', b'\xff.txt')
        self.path.write_bytes(patch(data, central(data)+8, 'H', 0x800))
        self.incomplete('invalid_name_encoding')

    def test_extra_fields_supported_and_unsupported(self):
        for extra, expected in ((b'\x01\x00\x00\x00', 'unsupported_zip64_or_unicode_override'),
                                (b'\x75\x70\x00\x00', 'unsupported_zip64_or_unicode_override'),
                                (b'\x55\x54\x04\x00x', 'malformed_extra_field')):
            with self.subTest(extra=extra):
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, 'w') as archive:
                    info = zipfile.ZipInfo('a.txt')
                    info.extra = extra
                    archive.writestr(info, b'toy')
                self.path.write_bytes(stream.getvalue())
                self.incomplete(expected)

    def test_uninterpreted_extra_field_review(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            info = zipfile.ZipInfo('a.txt')
            info.extra = b'\x55\x54\x00\x00'
            archive.writestr(info, b'toy')
        self.path.write_bytes(stream.getvalue())
        self.assertIn('uninterpreted_extra_fields', self.run_tool()[1]['archive']['entries'][0]['issues'])

    def test_bad_descriptor(self):
        data = descriptor_zip()
        pos = data.index(b'PK\x07\x08')
        self.path.write_bytes(patch(data, pos+4, 'I', 42))
        self.incomplete('descriptor_mismatch')

    def test_prepended_stub_rejected(self):
        data = self.path.read_bytes()
        start = central(data)
        data = patch(data, start+42, 'I', 4)
        data = patch(data, len(data)-6, 'I', start+4)
        self.path.write_bytes(b'stub'+data)
        self.incomplete('noncontiguous_or_overlapping_layout')

    def test_overlapping_records(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            data = build_zip([('a.txt', b'toy'), ('a.txt', b'toy')])
        start = central(data)
        self.path.write_bytes(patch(data, start+46+5+42, 'I', 0))
        self.incomplete('noncontiguous_or_overlapping_layout')

    def test_metadata_requests_skip_payload_except_bounded_tail(self):
        data = build_zip([('a.txt', b'x'*100000)])
        class Spy(io.BytesIO):
            def __init__(self, value):
                super().__init__(value)
                self.reads = []
            def read(self, count=-1):
                self.reads.append((self.tell(), count))
                return super().read(count)
        stream = Spy(data)
        tool.inspect_stream(stream, len(data), 'toy', tool.Budget())
        self.assertEqual(stream.reads[0], (len(data)-65557, 65557))
        for offset, count in stream.reads[1:]:
            self.assertTrue(offset+count <= 35 or offset >= central(data), (offset, count))

    def test_large_declared_total(self):
        data = build_zip([(str(i), b'x') for i in range(5)], zipfile.ZIP_DEFLATED)
        start, offset, position = central(data), 0, central(data)
        for i in range(5):
            data = patch(data, offset+22, 'I', 2*1024**3)
            data = patch(data, position+24, 'I', 2*1024**3)
            packed = struct.unpack_from('<I', data, position+20)[0]
            offset += 31+packed
            position += 47
        self.path.write_bytes(data)
        self.assertIn('large_declared_total', self.run_tool()[1]['archive']['issues'])

    def test_name_length_limit(self):
        self.path.write_bytes(build_zip([('x'*1025, b'toy')]))
        self.incomplete('name_or_central_entry_limit')

    def test_output_creation_race_never_overwrites(self):
        target = self.root/'report.json'
        target.write_bytes(b'Owned by someone else')
        with self.assertRaises(tool.Failure):
            tool.write(b'new data', target)
        self.assertEqual(target.read_bytes(), b'Owned by someone else')

    def test_output_exclusive_and_input_overlap(self):
        output = self.root/'report.json'
        self.assertEqual(self.run_tool('--output', output)[0], 0)
        before = output.read_bytes()
        self.assertEqual(self.run_tool('--output', output)[0], 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(self.run_tool('--output', self.path)[0], 1)

    def test_missing_parent_and_bad_args(self):
        self.assertEqual(self.run_tool('--output', self.root/'missing'/'report.json')[0], 1)
        self.assertEqual(self.run_tool('--unknown', 'private text')[0], 1)

    def test_linked_input_and_output_parent(self):
        link = self.root/'linked.zip'
        try:
            link.symlink_to(self.path)
        except OSError:
            self.skipTest('Native symlink creation unavailable')
        self.assertEqual(self.run_tool(archive=link)[0], 1)
        directory = self.root/'linked-folder'
        directory.symlink_to(self.root, target_is_directory=True)
        try:
            self.assertEqual(self.run_tool('--output', directory/'report.json')[0], 1)
        finally:
            directory.unlink()

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_windows_junction_rejected(self):
        target = self.root/'real'
        target.mkdir()
        (target/'data.zip').write_bytes(self.path.read_bytes())
        link = self.root/'junction'
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        result = subprocess.run(['powershell', '-NoProfile', '-Command',
            f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            self.skipTest('Native junction creation unavailable')
        self.assertTrue(link.lstat().st_file_attributes & 0x400)
        try:
            self.assertEqual(self.run_tool(archive=link/'data.zip')[0], 1)
            self.assertEqual(self.run_tool('--output', link/'report.json')[0], 1)
        finally:
            self.assertTrue(link.lstat().st_file_attributes & 0x400)
            link.rmdir()

    def test_path_policies(self):
        for value in ('//host/share/a.zip', 'C:relative.zip', 'NUL.zip', 'a:stream'):
            with self.subTest(value=value), self.assertRaises(tool.Failure):
                tool.local_path(value)

    def test_bounded_report_and_metadata_accounting(self):
        with mock.patch.object(tool, 'REPORT_LIMIT', 10), self.assertRaises(tool.Failure):
            tool.encode({'x': 'long content'})
        with mock.patch.object(tool, 'METADATA_LIMIT', 10), self.assertRaises(tool.Failure):
            tool.Budget().charge({'x': 'long content'})

    def test_read_limit(self):
        with self.assertRaises(tool.Failure):
            tool.region(io.BytesIO(b'ab'), 0, 2, 2, [tool.TOTAL_READ_LIMIT])

    def test_input_mutation_detected(self):
        original = tool.inspect_stream
        def mutate(*args):
            result = original(*args)
            with self.path.open('ab') as stream:
                stream.write(b'changed')
            return result
        args = tool.parser().parse_args(['--archive', 'toy='+str(self.path)])
        with mock.patch.object(tool, 'inspect_stream', side_effect=mutate):
            report, target = tool.inspect(args)
        self.assertFalse(report['complete'])
        self.assertEqual(report['errors'][0]['code'], 'input_changed')

    def test_example_generator_and_expected_codes(self):
        destination = self.root/'examples'
        result = subprocess.run([sys.executable, '-B', str(GENERATOR), '--destination', str(destination)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        for name, expected in (('clean.zip', 0), ('wrapper.zip', 2), ('review.zip', 2)):
            self.assertEqual(self.run_tool(archive=destination/name)[0], expected)
        result = subprocess.run([sys.executable, '-B', str(GENERATOR), '--destination', str(destination)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
