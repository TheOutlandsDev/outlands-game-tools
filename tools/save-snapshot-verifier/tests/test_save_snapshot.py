"""Original generated fixtures only; no games, user saves or network calls."""
import argparse
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

SCRIPT = Path(__file__).resolve().parents[1] / 'save_snapshot.py'
SPEC = importlib.util.spec_from_file_location('save_snapshot', SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='snapshot-original-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root/'original source'; self.source.mkdir()
        self.dest = self.root/'new snapshot'
        (self.source/'toy-save.dat').write_bytes(b'Original test save bytes\x00\x01')
        self.other = self.root/'toy config.ini'
        self.other.write_bytes(b'[original]\nvalue=private-fixture-value\n')

    def invoke(self, *arguments):
        run = subprocess.run([sys.executable,'-B',str(SCRIPT),*map(str,arguments)],
                             capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertNotIn('Traceback', run.stderr)
        return run

    def snapshot(self, *extra, code=0):
        return self.check(self.invoke('snapshot','--source',f'saves={self.source}',
                                     '--destination',self.dest,'--confirm-closed',*extra),code)

    def verify(self, *extra, code=0):
        return self.check(self.invoke('verify','--snapshot',self.dest,*extra),code)

    def check(self, run, code):
        self.assertEqual(run.returncode,code,run.stdout+run.stderr)
        report=json.loads(run.stdout)
        public=json.dumps(report)
        self.assertNotIn(str(self.root).replace('\\','\\\\'),public)
        self.assertNotIn('private-fixture-value',public)
        return report

    def test_help_version_without_dependencies(self):
        for option in ('--help','--version'):
            run=self.invoke(option)
            self.assertEqual(run.returncode,0,run.stderr)

    def test_snapshot_and_verify_multiple_sources_preserve_inputs(self):
        before=(self.source/'toy-save.dat').read_bytes(),self.other.read_bytes()
        result=self.snapshot('--source',f'config={self.other}')
        self.assertEqual(result['summary']['files'],2)
        self.assertTrue(result['summary']['copies_verified'])
        self.assertFalse((self.dest/'INCOMPLETE.json').exists())
        manifest=json.loads((self.dest/'manifest.json').read_text())
        for entry in manifest['files']:
            content=(self.dest/'data'/entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(),entry['sha256'])
        self.assertEqual(self.verify()['summary']['matched_files'],2)
        self.assertEqual(before,((self.source/'toy-save.dat').read_bytes(),self.other.read_bytes()))

    def test_nested_unicode_empty_file_and_multichunk_file(self):
        nested=self.source/'nested';nested.mkdir()
        (nested/'toy_雪.dat').write_bytes(b'')
        (nested/'many.dat').write_bytes(b'original '*160000)
        self.snapshot()
        self.assertEqual(self.verify()['summary']['matched_files'],3)

    def test_changed_missing_and_unexpected_are_findings(self):
        self.snapshot()
        data=self.dest/'data/saves'
        (data/'toy-save.dat').write_bytes(b'changed')
        self.assertEqual(self.verify(code=2)['differences'][0]['code'],'changed_file')
        (data/'toy-save.dat').unlink()
        (data/'extra.dat').write_bytes(b'original extra')
        codes={e['code'] for e in self.verify(code=2)['differences']}
        self.assertEqual(codes,{'missing_file','unexpected_file'})

    def test_existing_destination_never_overwritten(self):
        self.dest.mkdir(); sentinel=self.dest/'keep.dat';sentinel.write_bytes(b'keep')
        self.snapshot(code=1)
        self.assertEqual(list(self.dest.iterdir()),[sentinel])
        self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_confirmation_required_before_creating_destination(self):
        self.check(self.invoke('snapshot','--source',f'saves={self.source}',
                               '--destination',self.dest),1)
        self.assertFalse(self.dest.exists())

    def test_overlap_and_output_in_source_refused_before_copy(self):
        for extra in (['--destination',self.source/'nested'],['--output',self.source/'report.json']):
            self.snapshot(*extra,code=1)
            self.assertFalse(self.dest.exists())
        self.assertEqual(len(list(self.source.iterdir())),1)

    def test_output_inside_new_destination_refused_before_copy(self):
        self.snapshot('--output',self.dest/'report.json',code=1)
        self.assertFalse(self.dest.exists())

    def test_existing_report_refused_before_copy(self):
        output=self.root/'report.json';output.write_bytes(b'keep')
        self.snapshot('--output',output,code=1)
        self.assertFalse(self.dest.exists())
        self.assertEqual(output.read_bytes(),b'keep')

    def test_new_report_and_verify_report_written_exclusively(self):
        output=self.root/'snapshot-report.json'
        run=self.invoke('snapshot','--source',f'saves={self.source}',
                        '--destination',self.dest,'--confirm-closed','--output',output)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(run.stdout,'')
        self.assertTrue(json.loads(output.read_text())['summary']['complete'])
        before=output.read_bytes()
        self.check(self.invoke('verify','--snapshot',self.dest,'--output',output),1)
        self.assertEqual(before,output.read_bytes())

    def test_no_report_inside_snapshot(self):
        self.snapshot()
        self.verify('--output',self.dest/'report.json',code=1)
        self.assertFalse((self.dest/'report.json').exists())

    def test_missing_source_and_empty_selection(self):
        self.snapshot('--source',f'none={self.root/"missing"}',code=1)
        (self.source/'toy-save.dat').unlink()
        self.snapshot(code=1)
        self.assertFalse(self.dest.exists())

    def test_duplicate_or_unsafe_labels(self):
        for label in ('saves','SAVES','../escape','NUL','bad space'):
            self.snapshot('--source',f'{label}={self.other}',code=1)
            self.assertFalse(self.dest.exists())

    def test_overlapping_source_roots(self):
        self.snapshot('--source',f'all={self.root}',code=1)
        self.assertFalse(self.dest.exists())

    def test_byte_and_entry_limits_before_copy(self):
        for flag in ('--max-file-bytes','--max-total-bytes'):
            self.snapshot(flag,'1',code=1)
            self.assertFalse(self.dest.exists())
        (self.source/'another.dat').write_bytes(b'x')
        self.snapshot('--max-entries','1',code=1)

    def test_invalid_limits_fail_without_traceback(self):
        for value in ('0','-1','bad',str(sys.maxsize),str(10**100)):
            run=self.invoke('verify','--snapshot',self.dest,'--max-file-bytes',value)
            self.assertEqual(run.returncode,1)

    def test_network_device_and_stream_paths_refused(self):
        for value in ('//server/share/snapshot','NUL','output.json:extra'):
            self.check(self.invoke('verify','--snapshot',value),1)

    def test_partial_snapshot_is_never_verified(self):
        self.dest.mkdir();(self.dest/'INCOMPLETE.json').write_text('{}')
        self.verify(code=1)

    def test_data_layout_must_be_directory(self):
        self.snapshot()
        (self.dest/'data/saves/toy-save.dat').unlink()
        (self.dest/'data/saves').rmdir()
        (self.dest/'data').rmdir()
        (self.dest/'data').write_bytes(b'not a data directory')
        result=self.verify(code=1)
        self.assertFalse(result['summary']['complete'])

    def test_manifest_traversal_and_duplicate_paths_refused(self):
        self.snapshot();path=self.dest/'manifest.json';original=path.read_text()
        for key in ('../outside','saves/../outside','/absolute','saves/a\\b','saves/NUL'):
            data=json.loads(original);data['files'][0]['path']=key;path.write_text(json.dumps(data))
            self.verify(code=1)
        data=json.loads(original);data['files'].append(dict(data['files'][0]));path.write_text(json.dumps(data))
        self.verify(code=1)

    def test_manifest_types_hashes_and_schema_are_validated(self):
        self.snapshot();path=self.dest/'manifest.json';original=path.read_text()
        for field,value in (('bytes',True),('bytes',-1),('sha256','not-hash')):
            data=json.loads(original);data['files'][0][field]=value;path.write_text(json.dumps(data))
            self.verify(code=1)
        data=json.loads(original);data['schema_version']=True;path.write_text(json.dumps(data))
        self.verify(code=1)

    def test_untrusted_extra_manifest_fields_are_not_echoed(self):
        self.snapshot();path=self.dest/'manifest.json';data=json.loads(path.read_text())
        data['private-extra']='private-fixture-value';path.write_text(json.dumps(data))
        self.verify()

    def test_unexpected_snapshot_root_content_is_incomplete(self):
        self.snapshot();(self.dest/'unknown.json').write_text('{}')
        self.verify(code=1)

    def test_manifest_limit_and_actual_data_total_limit(self):
        self.snapshot()
        self.verify('--max-total-bytes','1',code=1)
        path=self.dest/'manifest.json';path.write_bytes(b' '*(TOOL.MAX_MANIFEST+1))
        self.verify(code=1)

    def test_file_link_is_refused_when_platform_can_create_it(self):
        link=self.source/'linked.dat'
        try: link.symlink_to(self.other)
        except OSError: self.skipTest('Account cannot create file symlinks')
        self.snapshot(code=1)
        self.assertFalse(self.dest.exists())

    def test_directory_link_is_refused_when_platform_can_create_it(self):
        outside=self.root/'outside';outside.mkdir();(outside/'keep.dat').write_bytes(b'keep')
        link=self.source/'link'
        try: link.symlink_to(outside,target_is_directory=True)
        except OSError: self.skipTest('Account cannot create directory symlinks')
        self.snapshot(code=1)
        self.assertFalse(self.dest.exists())

    def test_case_collision_is_refused_on_supporting_filesystem(self):
        a,b=self.source/'Case.dat',self.source/'case.dat';a.write_bytes(b'a');b.write_bytes(b'b')
        if len([p for p in self.source.iterdir() if p.name.casefold()=='case.dat'])!=2:
            self.skipTest('Filesystem does not support case-colliding fixtures')
        self.snapshot(code=1)

    def test_interrupted_copy_leaves_incomplete_marker_and_original(self):
        original=(self.source/'toy-save.dat').read_bytes()
        args=argparse.Namespace(source=[f'saves={self.source}'],destination=str(self.dest),output=None,
                                max_file_bytes=TOOL.DEFAULT_FILE,max_total_bytes=TOOL.DEFAULT_TOTAL,
                                max_entries=TOOL.DEFAULT_COUNT,confirm_closed=True)
        with patch.object(TOOL,'digest',side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError): TOOL.create_snapshot(args,TOOL.report('snapshot'))
        self.assertTrue((self.dest/'INCOMPLETE.json').is_file())
        self.assertFalse((self.dest/'manifest.json').exists())
        self.assertEqual(original,(self.source/'toy-save.dat').read_bytes())
        self.verify(code=1)

    def test_source_mutation_during_snapshot_prevents_complete_manifest(self):
        args=argparse.Namespace(source=[f'saves={self.source}'],destination=str(self.dest),output=None,
                                max_file_bytes=TOOL.DEFAULT_FILE,max_total_bytes=TOOL.DEFAULT_TOTAL,
                                max_entries=TOOL.DEFAULT_COUNT,confirm_closed=True)
        real=TOOL.digest
        def mutate(path,limit):
            value=real(path,limit)
            (self.source/'newly-added.dat').write_bytes(b'changed membership')
            return value
        with patch.object(TOOL,'digest',side_effect=mutate):
            with self.assertRaises(TOOL.Failure): TOOL.create_snapshot(args,TOOL.report('snapshot'))
        self.assertTrue((self.dest/'INCOMPLETE.json').exists())
        self.assertFalse((self.dest/'manifest.json').exists())


if __name__=='__main__': unittest.main()
