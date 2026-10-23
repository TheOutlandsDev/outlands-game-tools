"""Original generated evidence only; no live process, installed game or private logs. MIT."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/'session_auditor.py'
GENERATOR = SCRIPT.parent/'examples/create_example.py'
fixtures = runpy.run_path(str(GENERATOR))
spec = importlib.util.spec_from_file_location('session_auditor', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='session-audit-')
        self.root = Path(self.temp.name)
        self.evidence = self.root/'session'
        self.document = fixtures['create_session'](self.evidence)
        self.manifest = self.evidence/'manifest.json'

    def tearDown(self):
        self.temp.cleanup()

    def save_manifest(self):
        self.manifest.write_bytes(fixtures['json_bytes'](self.document))

    def change_receipt(self, role, **changes):
        reference = self.document['receipts'][role]
        path = self.evidence/reference['path']
        document = json.loads(path.read_bytes())
        document.update(changes)
        data = fixtures['json_bytes'](document)
        path.write_bytes(data)
        self.document['receipts'][role] = fixtures['file_reference'](reference['path'], data)
        self.save_manifest()

    def run_tool(self, *options, root=None, manifest=None):
        args = [sys.executable, '-B', str(SCRIPT), '--root', str(root or self.evidence), '--manifest', str(manifest or self.manifest)]
        args.extend(str(value) for value in options)
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        text = result.stdout
        if not text and '--output' in args:
            output = Path(args[args.index('--output')+1])
            if output.is_file():
                text = output.read_text(encoding='utf-8')
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn(str(self.root), text+result.stderr)
        self.assertTrue(text, result.stderr)
        return result.returncode, json.loads(text)

    def incomplete(self, code):
        status, report = self.run_tool()
        self.assertEqual(status, 1)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['manifest'])
        self.assertIsNone(report['session'])
        self.assertEqual(report['files'], [])
        self.assertEqual(report['findings'], [])
        self.assertIn(code, [row['code'] for row in report['errors']])

    def codes(self, report):
        return {row['code'] for row in report['findings']}

    def test_clean_hashes_session_and_input_preservation(self):
        before = {p.relative_to(self.evidence).as_posix(): p.read_bytes() for p in self.evidence.rglob('*') if p.is_file()}
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertTrue(report['complete'])
        self.assertEqual(report['summary']['verified_files'], 3)
        self.assertTrue(report['session']['receipt_pair_consistent'])
        self.assertEqual(report['session']['duration_seconds'], 120)
        self.assertEqual(report['session']['exit_code'], 0)
        self.assertEqual(report['summary']['evidence_bytes_read'], sum(row['actual_bytes'] for row in report['files']))
        after = {p.relative_to(self.evidence).as_posix(): p.read_bytes() for p in self.evidence.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_report_omits_receipt_identity_fields_and_raw_data(self):
        report = self.run_tool()[1]
        text = json.dumps(report)
        for private in ('1234', 'toy-game', '2026-01-01T12:', 'Original fictional session capture'):
            self.assertNotIn(private, text)
        self.assertFalse(report['policy']['authenticity_or_gameplay_attested'])

    def test_changed_capture_size_and_hash(self):
        (self.evidence/'captures/toy.log').write_bytes(b'changed')
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(self.codes(report), {'size_mismatch', 'hash_mismatch'})
        self.assertTrue(report['session']['receipt_pair_consistent'])

    def test_same_size_capture_change(self):
        path = self.evidence/'captures/toy.log'
        data = path.read_bytes()
        path.write_bytes(b'X'+data[1:])
        self.assertEqual(self.codes(self.run_tool()[1]), {'hash_mismatch'})

    def test_bad_declared_size_with_matching_digest(self):
        self.document['captures'][0]['bytes'] += 1
        self.save_manifest()
        self.assertEqual(self.codes(self.run_tool()[1]), {'size_mismatch'})

    def test_missing_capture_and_parent_directory(self):
        self.document['captures'][0]['path'] = 'missing-parent/toy.log'
        self.save_manifest()
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertIn('missing_file', self.codes(report))
        self.assertEqual(report['summary']['missing_files'], 1)

    def test_missing_receipt_reference(self):
        self.document['receipts']['exit'] = None
        self.save_manifest()
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(self.codes(report), {'missing_receipt'})
        self.assertEqual(report['session']['exit_status'], 'missing')
        self.assertIsNone(report['session']['receipt_pair_consistent'])

    def test_missing_receipt_file(self):
        (self.evidence/'receipts/exit.json').unlink()
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertIn('missing_file', self.codes(report))
        self.assertEqual(report['session']['exit_status'], 'missing')

    def test_unverified_receipt_is_never_parsed(self):
        (self.evidence/'receipts/exit.json').write_bytes(b'not JSON')
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(report['session']['exit_status'], 'unverified')
        self.assertNotIn('invalid_receipt', self.codes(report))
        self.assertIsNone(report['session']['exit_code'])

    def test_verified_but_malformed_receipt_is_review_finding(self):
        data = b'not JSON'
        (self.evidence/'receipts/exit.json').write_bytes(data)
        self.document['receipts']['exit'] = fixtures['file_reference']('receipts/exit.json', data)
        self.save_manifest()
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertTrue(report['complete'])
        self.assertEqual(report['session']['exit_status'], 'invalid')
        self.assertIn('invalid_receipt', self.codes(report))

    def test_verified_receipt_depth_limit_is_incomplete(self):
        data = b'['*9+b']'*9
        (self.evidence/'receipts/exit.json').write_bytes(data)
        self.document['receipts']['exit'] = fixtures['file_reference']('receipts/exit.json', data)
        self.save_manifest()
        self.incomplete('json_depth_limit')

    def test_receipt_session_process_executable_and_time_mismatch(self):
        self.change_receipt('exit', session_id='other-session', process_id=4321,
                            executable_id='different-game', timestamp_utc='2026-01-01T11:00:00Z')
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(self.codes(report), {'session_id_mismatch', 'process_id_mismatch', 'executable_id_mismatch', 'exit_before_launch'})
        self.assertFalse(report['session']['receipt_pair_consistent'])
        self.assertEqual(report['session']['duration_seconds'], -3600)

    def test_nonzero_exit_is_observation_not_pair_inconsistency(self):
        for code in (-1, 7, 3221225477, 0xFFFFFFFF):
            with self.subTest(code=code):
                self.change_receipt('exit', exit_code=code)
                status, report = self.run_tool()
                self.assertEqual(status, 2)
                self.assertEqual(self.codes(report), {'nonzero_exit_code'})
                self.assertTrue(report['session']['receipt_pair_consistent'])
                self.assertEqual(report['session']['exit_code'], code)

    def test_identical_times_and_leap_day(self):
        self.change_receipt('launch', timestamp_utc='2024-02-29T00:00:00Z')
        self.change_receipt('exit', timestamp_utc='2024-02-29T00:00:00Z')
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(self.run_tool()[1]['session']['duration_seconds'], 0)

    def test_receipt_schema_timestamp_and_scalar_boundaries(self):
        changes = ({'schema_version': True}, {'event':'launch'}, {'process_id':True}, {'process_id':0},
                   {'process_id':0x80000000}, {'executable_id':'path/to/game'}, {'exit_code':True},
                   {'exit_code':-0x80000001}, {'exit_code':0x100000000}, {'extra':1},
                   {'timestamp_utc':'2025-02-29T00:00:00Z'}, {'timestamp_utc':'2026-01-01T00:00:00+00:00'},
                   {'timestamp_utc':'2026-01-01T00:00:00.1Z'}, {'timestamp_utc':'2026-01-01T00:00:60Z'})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(tool.Failure):
                tool.receipt_document(fixtures['json_bytes'](fixtures['receipt']('exit', **change)), 'exit')

    def test_no_captures_is_explicit_review_coverage(self):
        self.document['captures'] = []
        self.save_manifest()
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(self.codes(report), {'no_captures'})

    def test_unlisted_files_are_not_read_or_inventoried(self):
        (self.evidence/'private-extra.txt').write_text('private extra data', encoding='utf-8')
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertEqual(report['summary']['selected_files'], 3)
        self.assertNotIn('private-extra', json.dumps(report))

    def test_unsafe_relative_paths(self):
        for path in ('../outside', '/absolute', 'C:/drive', 'a\\b', 'a//b', 'NUL.txt', 'a:stream', 'a./x',
                     'a\x00b', 'caf\u00e9.log', '/'.join(['x']*33)):
            with self.subTest(path=path):
                self.document['captures'][0]['path'] = path
                self.save_manifest()
                self.incomplete('unsafe_relative_path')

    def test_duplicate_case_and_prefix_references_rejected(self):
        row = self.document['captures'][0]
        for path, expected in (('CAPTURES/TOY.LOG','duplicate_or_case_colliding_path'),
                               ('captures','file_directory_path_collision')):
            self.document['captures'] = [row, {**row, 'path':path}]
            self.save_manifest()
            self.incomplete(expected)

    def test_receipt_reference_cannot_reuse_capture(self):
        self.document['receipts']['exit'] = self.document['captures'][0].copy()
        self.save_manifest()
        self.incomplete('duplicate_or_case_colliding_path')

    def test_manifest_self_reference_refused(self):
        self.document['captures'][0]['path'] = 'manifest.json'
        self.save_manifest()
        self.incomplete('manifest_overlaps_evidence')

    def test_hash_and_size_schema_are_strict(self):
        for changes, expected in (({'sha256':'A'*64},'invalid_sha256'), ({'bytes':True},'invalid_declared_size'),
                                  ({'bytes':-1},'invalid_declared_size'), ({'unknown':1},'invalid_or_unknown_fields')):
            self.document['captures'] = [{**fixtures['file_reference']('captures/toy.log', b'toy'), **changes}]
            self.save_manifest()
            self.incomplete(expected)

    def test_declared_file_total_and_count_limits(self):
        self.document['captures'][0]['bytes'] = tool.CAPTURE_LIMIT+1
        self.save_manifest(); self.incomplete('declared_file_byte_limit')
        row = fixtures['file_reference']('captures/toy.log', b'toy')
        self.document['captures'] = [{**row, 'path':f'f{i}', 'bytes':tool.CAPTURE_LIMIT} for i in range(5)]
        self.save_manifest(); self.incomplete('declared_total_byte_limit')
        self.document['captures'] = [{**row, 'path':f'f{i}'} for i in range(tool.CAPTURE_COUNT+1)]
        self.save_manifest(); self.incomplete('capture_count_limit')

    def test_actual_file_size_and_total_limits_before_hashing(self):
        with mock.patch.object(tool, 'CAPTURE_LIMIT', 2), self.assertRaises(tool.Failure):
            tool.hash_evidence(self.evidence/'captures/toy.log', self.document['captures'][0], 'capture', [0])
        with self.assertRaises(tool.Failure):
            tool.hash_evidence(self.evidence/'captures/toy.log', self.document['captures'][0], 'capture', [tool.TOTAL_LIMIT])

    def test_stream_hash_chunk_bound_and_binary_bytes(self):
        data = bytes(range(256))*10000
        path = self.evidence/'captures/toy.log'; path.write_bytes(data)
        reference = fixtures['file_reference']('captures/toy.log', data)
        requests, fdopen = [], tool.os.fdopen
        class ReadSpy:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def fileno(self): return self.stream.fileno()
            def read(self, count): requests.append(count); return self.stream.read(count)
        with mock.patch.object(tool.os, 'fdopen', side_effect=lambda *a, **k: ReadSpy(fdopen(*a, **k))):
            row, content, info = tool.hash_evidence(path, reference, 'capture', [0])
        self.assertEqual(row['actual_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(row['status'], 'verified')
        self.assertIsNone(content)
        self.assertTrue(requests)
        self.assertTrue(all(0 < count <= tool.CHUNK for count in requests))

    def test_empty_capture_is_valid_hashable_evidence(self):
        path = self.evidence/'captures/toy.log'; path.write_bytes(b'')
        self.document['captures'] = [fixtures['file_reference']('captures/toy.log', b'')]
        self.save_manifest()
        self.assertEqual(self.run_tool()[0], 0)

    def test_malformed_manifest_keys_depth_encoding_and_bytes(self):
        cases = ((b'{"schema_version":1,"schema_version":1}', 'duplicate_json_key'),
                 (b'['*9+b']'*9,'json_depth_limit'), (b'\xff','unsupported_encoding'),
                 (b' '* (tool.FILE_LIMIT+1),'file_byte_limit'),
                 (b'{"schema_version":NaN}','invalid_json_number'))
        for data, code in cases:
            with self.subTest(code=code):
                self.manifest.write_bytes(data); self.incomplete(code)

    def test_manifest_unknown_fields_version_and_session_label(self):
        for change, expected in (({'schema_version':True},'unsupported_schema_version'),
                                 ({'extra':'private'},'invalid_or_unknown_fields'),
                                 ({'session_id':'bad id'},'invalid_label')):
            self.save_manifest()
            document = {**self.document, **change}
            self.manifest.write_bytes(fixtures['json_bytes'](document))
            self.incomplete(expected)

    def test_external_report_exclusive_and_input_protection(self):
        output = self.root/'report.json'
        self.assertEqual(self.run_tool('--output', output)[0], 0)
        original = output.read_bytes()
        self.assertEqual(self.run_tool('--output', output)[0], 1)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(self.run_tool('--output', self.manifest)[0], 1)
        status, report = self.run_tool('--output', self.evidence/'new-report.json')
        self.assertEqual(status, 1)
        self.assertEqual(report['errors'][0]['code'], 'output_inside_evidence_root')
        self.assertFalse((self.evidence/'new-report.json').exists())

    def test_missing_root_manifest_output_parent_and_directory_file(self):
        self.assertEqual(self.run_tool(root=self.root/'absent')[0], 1)
        self.assertEqual(self.run_tool(manifest=self.root/'absent')[0], 1)
        self.assertEqual(self.run_tool('--output', self.root/'absent'/'report.json')[0], 1)
        self.document['captures'][0]['path'] = 'captures'
        self.save_manifest(); self.incomplete('not_a_regular_file')

    def test_invalid_args_and_paths_sanitized(self):
        self.assertEqual(self.run_tool('--unknown', 'private')[0], 1)
        for value in ('//host/share/file','C:relative','NUL.json','a:stream'):
            with self.subTest(value=value), self.assertRaises(tool.Failure):tool.local_path(value)

    def test_manifest_change_during_audit_drops_results(self):
        original = tool.hash_evidence
        def mutate(*args):
            result = original(*args)
            self.manifest.write_bytes(b'changed')
            return result
        args = tool.parser().parse_args(['--root',str(self.evidence),'--manifest',str(self.manifest)])
        with mock.patch.object(tool, 'hash_evidence', side_effect=mutate):report, target = tool.inspect(args)
        self.assertFalse(report['complete']); self.assertEqual(report['files'], [])
        self.assertEqual(report['errors'][0]['code'], 'input_changed')

    def test_capture_changed_after_hash_drops_results(self):
        original = tool.hash_evidence
        def mutate(*args):
            result = original(*args)
            if args[2] == 'exit':
                (self.evidence/'captures/toy.log').write_bytes(b'changed after capture hashing')
            return result
        args = tool.parser().parse_args(['--root',str(self.evidence),'--manifest',str(self.manifest)])
        with mock.patch.object(tool, 'hash_evidence', side_effect=mutate):report, target = tool.inspect(args)
        self.assertFalse(report['complete']); self.assertEqual(report['files'], [])
        self.assertEqual(report['errors'][0]['code'], 'input_changed')

    def test_read_failure_is_incomplete_without_raw_exception(self):
        stdout = io.StringIO()
        with mock.patch.object(tool, 'hash_evidence', side_effect=OSError('private device detail')), contextlib.redirect_stdout(stdout):
            status = tool.main(['--root',str(self.evidence),'--manifest',str(self.manifest)])
        report = json.loads(stdout.getvalue())
        self.assertEqual(status, 1); self.assertFalse(report['complete']); self.assertEqual(report['files'], [])
        self.assertNotIn('private device',stdout.getvalue())

    def test_receipt_file_size_limit_before_parse(self):
        path = self.evidence/'receipts/exit.json'
        path.write_bytes(b' ' * (tool.RECEIPT_LIMIT+1))
        self.incomplete('evidence_file_byte_limit')

    def test_manifest_bom_and_receipt_bom(self):
        self.manifest.write_bytes(b'\xef\xbb\xbf'+self.manifest.read_bytes())
        self.assertEqual(self.run_tool()[0], 0)
        path = self.evidence/'receipts/exit.json'
        data = b'\xef\xbb\xbf'+path.read_bytes(); path.write_bytes(data)
        self.document['receipts']['exit'] = fixtures['file_reference']('receipts/exit.json',data)
        self.save_manifest()
        self.assertEqual(self.run_tool()[0], 0)

    def test_missing_file_appearing_during_audit_is_change(self):
        path = self.evidence/'captures/toy.log'; path.unlink()
        original = tool.hash_evidence
        def appear(*args):
            result = original(*args)
            if args[2] == 'exit':path.write_bytes(b'appeared')
            return result
        args = tool.parser().parse_args(['--root',str(self.evidence),'--manifest',str(self.manifest)])
        with mock.patch.object(tool, 'hash_evidence', side_effect=appear):report, target = tool.inspect(args)
        self.assertFalse(report['complete']); self.assertEqual(report['files'], [])
        self.assertEqual(report['errors'][0]['code'], 'input_changed')

    def test_output_and_metadata_limit_fallback(self):
        with mock.patch.object(tool,'METADATA_LIMIT',10),self.assertRaises(tool.Failure):
            tool.manifest_document(self.manifest.read_bytes(),tool.Budget())
        cap = len(tool.encode(tool.blank()))+100
        stdout = io.StringIO()
        with mock.patch.object(tool,'REPORT_LIMIT',cap),contextlib.redirect_stdout(stdout):
            status = tool.main(['--root',str(self.evidence),'--manifest',str(self.manifest)])
        report=json.loads(stdout.getvalue())
        self.assertEqual(status,1); self.assertFalse(report['complete']); self.assertEqual(report['files'],[])
        self.assertEqual(report['errors'][0]['code'],'report_byte_limit')

    def test_deterministic_report(self):
        self.assertEqual(self.run_tool()[1],self.run_tool()[1])

    def test_linked_input_and_output_parent_rejected(self):
        path=self.evidence/'captures/toy.log'; link=self.evidence/'capture-link.log'
        try:link.symlink_to(path)
        except OSError:self.skipTest('Native symlink creation unavailable')
        self.document['captures'][0]['path']='capture-link.log';self.save_manifest()
        self.assertEqual(self.run_tool()[0],1)
        folder=self.root/'linked-folder';folder.symlink_to(self.root,target_is_directory=True)
        try:self.assertEqual(self.run_tool('--output',folder/'report.json')[0],1)
        finally:folder.unlink()

    @unittest.skipUnless(os.name=='nt','Windows junction fixture')
    def test_windows_junction_root_and_output_rejected(self):
        link=self.root/'junction'
        escaped_link,escaped_target=str(link).replace("'","''"),str(self.evidence).replace("'","''")
        result=subprocess.run(['powershell','-NoProfile','-Command',
            f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
            capture_output=True,text=True,timeout=20)
        if result.returncode:self.skipTest('Native junction creation unavailable')
        self.assertTrue(link.lstat().st_file_attributes&0x400)
        try:
            self.assertEqual(self.run_tool(root=link)[0],1)
            self.assertEqual(self.run_tool('--output',link/'report.json')[0],1)
        finally:
            self.assertTrue(link.lstat().st_file_attributes&0x400);link.rmdir()

    def test_output_race_preserves_existing_file(self):
        output=self.root/'report.json';output.write_bytes(b'owned elsewhere')
        with self.assertRaises(tool.Failure):tool.write(b'new',output)
        self.assertEqual(output.read_bytes(),b'owned elsewhere')

    def test_original_example_commands(self):
        folder=self.root/'examples'
        result=subprocess.run([sys.executable,'-B',str(GENERATOR),'--destination',str(folder)],capture_output=True)
        self.assertEqual(result.returncode,0)
        for mode, expected in (('clean',0),('changed-capture',2),('missing-exit',2),('inconsistent',2)):
            status,report=self.run_tool(root=folder/mode,manifest=folder/mode/'manifest.json')
            self.assertEqual(status,expected)
        before=(folder/'clean/manifest.json').read_bytes()
        result=subprocess.run([sys.executable,'-B',str(GENERATOR),'--destination',str(folder)],capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual((folder/'clean/manifest.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
