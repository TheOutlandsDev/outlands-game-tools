"""Original generated PAK metadata fixtures; no game files or external parsers. MIT."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'pak_inspector.py'
GENERATOR = SCRIPT.parent / 'examples/create_example.py'
FIXTURE = runpy.run_path(str(GENERATOR))['build_pak']
MOUNT, NAME = '../../../', 'Toy/Content/a.uasset'


def footer(data):
    return struct.unpack('<Iiqq20s', data[-44:])


def change_index(data, callback):
    magic, version, start, size, digest = footer(data)
    index = bytearray(data[start:start+size])
    callback(index)
    return data[:start] + index + struct.pack('<Iiqq20s', magic, version, start, len(index), hashlib.sha1(index).digest())


def record_position(path=NAME, mount=MOUNT):
    return 4 + len(mount) + 1 + 4 + 4 + len(path) + 1


class PakTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pak-inspector-')
        self.root = Path(self.temp.name)
        self.a, self.b = self.root/'a.pak', self.root/'b.pak'
        self.a.write_bytes(FIXTURE([(NAME, b'Original toy data')]))
        self.b.write_bytes(FIXTURE([('Toy/Content/b.txt', b'Different original toy data')]))

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *options, selected=None):
        selected = [('base', self.a)] if selected is None else selected
        args = [sys.executable, '-B', str(SCRIPT)]
        for label, path in selected:
            args += ['--pak', label+'='+str(path)]
        args += [str(value) for value in options]
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
        self.assertNotIn('Traceback', result.stderr)
        text = result.stdout
        if not text and '--output' in args:
            output = Path(args[args.index('--output')+1])
            if output.is_file():
                text = output.read_text(encoding='utf-8')
        self.assertTrue(text, result.stderr)
        self.assertNotIn(str(self.root), text+result.stderr)
        return result, json.loads(text)

    def incomplete(self, report, code):
        self.assertFalse(report['complete'])
        self.assertIn(code, {row['code'] for row in report['errors']})
        self.assertEqual(report['paks'], [])
        self.assertEqual(report['conflicts'], [])

    def mutate_record(self, fmt, offset, value):
        data = self.a.read_bytes()
        self.a.write_bytes(change_index(data, lambda index: struct.pack_into('<'+fmt, index, record_position()+offset, value)))

    def test_single_stored_index_and_exact_metadata(self):
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report['complete'])
        entry = report['paks'][0]['entries'][0]
        self.assertEqual(entry['virtual_path'], NAME)
        self.assertEqual(entry['offset'], 0)
        self.assertEqual(entry['header_bytes'], 53)
        self.assertEqual(entry['stored_bytes'], len(b'Original toy data'))
        self.assertEqual(entry['compression_method'], 0)
        self.assertTrue(report['paks'][0]['index']['hash_verified'])
        self.assertFalse(report['policy']['payloads_read'])
        self.assertFalse(report['policy']['local_headers_checked'])

    def test_empty_archive_is_valid_and_narrow(self):
        self.a.write_bytes(FIXTURE([]))
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['entries'], 0)

    def test_two_disjoint_archives_have_no_conflicts(self):
        result, report = self.run_tool(selected=[('base', self.a), ('mod', self.b)])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['unique_paths'], 2)

    def test_overlap_uses_combined_mount_and_entry(self):
        self.b.write_bytes(FIXTURE([('a.uasset', b'changed')], mount='../../../Toy/Content/'))
        result, report = self.run_tool(selected=[('base', self.a), ('mod', self.b)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report['summary']['path_overlaps'], 1)
        self.assertEqual(report['conflicts'][0]['path'], NAME.lower())
        self.assertEqual(report['conflicts'][0]['providers'], [{'pak':'base','entry':0}, {'pak':'mod','entry':0}])
        self.assertFalse(report['policy']['load_order_inferred'])

    def test_overlap_is_reported_even_when_declared_hashes_match(self):
        self.b.write_bytes(self.a.read_bytes())
        result, report = self.run_tool(selected=[('base', self.a), ('mod', self.b)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report['summary']['path_overlaps'], 1)

    def test_case_variation_is_an_overlap_under_explicit_policy(self):
        self.b.write_bytes(FIXTURE([(NAME.upper(), b'toy')]))
        result, report = self.run_tool(selected=[('base',self.a),('mod',self.b)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report['paks'][1]['entries'][0]['virtual_path'], NAME.upper())

    def test_file_directory_conflict_with_intervening_sibling(self):
        self.a.write_bytes(FIXTURE([('Toy/a', b'x'), ('Toy/a.b', b'x')]))
        self.b.write_bytes(FIXTURE([('Toy/a/child.txt', b'y')]))
        result, report = self.run_tool(selected=[('base',self.a),('mod',self.b)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report['summary']['file_directory_conflicts'], 1)
        self.assertEqual(report['conflicts'][0]['descendant'], 'toy/a/child.txt')

    def test_internal_file_directory_collision_is_incomplete(self):
        self.a.write_bytes(FIXTURE([('Toy/a',b'x'),('Toy/a.b',b'x'),('Toy/a/child',b'y')]))
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.incomplete(report, 'internal_file_directory_collision')

    def test_duplicate_and_case_colliding_entries_are_refused(self):
        for path in (NAME, NAME.upper()):
            with self.subTest(path=path):
                self.a.write_bytes(FIXTURE([(NAME,b'x'),(path,b'y')]))
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.incomplete(report, 'duplicate_or_case_colliding_entry')
                self.assertEqual(report['errors'][0]['entry'], 1)

    def test_compressed_single_and_multiple_absolute_blocks_are_metadata_only(self):
        for payload in (b'Original toy compressed text', b'a'*70000):
            with self.subTest(size=len(payload)):
                self.a.write_bytes(FIXTURE([(NAME,payload)], compressed=True))
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 0)
                entry = report['paks'][0]['entries'][0]
                self.assertEqual(entry['block_count'], (len(payload)+65535)//65536)
                self.assertEqual(entry['uncompressed_bytes'], len(payload))

    def test_compression_method_number_is_not_a_decoder_claim(self):
        self.a.write_bytes(FIXTURE([(NAME,b'toy')], compressed=True))
        self.mutate_record('I', 24, 0x123)
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['paks'][0]['entries'][0]['compression_method'], 0x123)

    def test_utf16_encoded_ascii_names_are_supported(self):
        self.a.write_bytes(FIXTURE([(NAME,b'toy')], wide=True))
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['paks'][0]['entries'][0]['virtual_path'], NAME)

    def test_non_ascii_asset_names_are_explicitly_unsupported(self):
        self.a.write_bytes(FIXTURE([('Toy/caf\u00e9.txt', b'x')], wide=True))
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.incomplete(report, 'unsafe_virtual_path')

    def test_unsafe_entry_paths_are_never_normalized_or_extracted(self):
        for path in ('../a', '/a', 'Toy//a', 'Toy/./a', 'Toy/../a', 'Toy\\a',
                     'Toy/a:', 'Toy/a.', 'Toy/CON.txt', 'Toy/a ', 'a/'*65+'x'):
            with self.subTest(path=path):
                self.a.write_bytes(FIXTURE([(path,b'toy')]))
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.incomplete(report, 'unsafe_virtual_path')

    def test_unsupported_mounts_and_unsafe_mount_suffixes(self):
        for mount in ('', '/', '../../', '../../../../', '../../../Toy/../', '../../../Toy//', '../../../Toy'):
            with self.subTest(mount=mount):
                self.a.write_bytes(FIXTURE([(NAME,b'x')], mount=mount))
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_index_hash_mismatch_is_not_ignored(self):
        data = bytearray(self.a.read_bytes())
        start = footer(data)[2]
        data[start+4] ^= 1
        self.a.write_bytes(data)
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.incomplete(report, 'index_hash_mismatch')

    def test_source_unchanged_and_only_index_fingerprinted(self):
        before = self.a.read_bytes()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.a.read_bytes(), before)
        start,size = footer(before)[2:4]
        self.assertEqual(report['paks'][0]['index']['sha256'], hashlib.sha256(before[start:start+size]).hexdigest())
        self.assertNotIn('Original toy data', result.stdout)

    def test_payload_and_local_header_changes_are_not_validation_claims(self):
        first, _ = self.run_tool()
        data = bytearray(self.a.read_bytes())
        data[0] ^= 0x7f  # Local header is deliberately not read by this inspector.
        data[53] ^= 0x7f  # Payload is deliberately not read either.
        self.a.write_bytes(data)
        second, report = self.run_tool()
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        self.assertFalse(report['policy']['local_headers_checked'])

    def test_reader_only_requests_footer_and_index_regions(self):
        module = runpy.run_path(str(SCRIPT))
        globals_ = module['inspect_pak'].__globals__
        original = globals_['region']
        calls = []
        def observed(stream, offset, size):
            calls.append((offset,size))
            return original(stream,offset,size)
        globals_['region'] = observed
        try:
            report, unused = module['inspect'](module['parser']().parse_args(['--pak','toy='+str(self.a)]))
        finally:
            globals_['region'] = original
        self.assertTrue(report['complete'])
        data=self.a.read_bytes()
        self.assertEqual(calls, [(len(data)-44,44), footer(data)[2:4]])

    def test_bad_magic_and_truncated_footer(self):
        for data in (b'', b'x'*43, b'x'*44):
            with self.subTest(size=len(data)):
                self.a.write_bytes(data)
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_all_other_footer_versions_are_refused(self):
        original=self.a.read_bytes()
        for version in (1,2,4,7,8,11,12,-1):
            with self.subTest(version=version):
                data=bytearray(original)
                struct.pack_into('<i',data,len(data)-40,version)
                self.a.write_bytes(data)
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.incomplete(report, 'unsupported_pak_version')

    def test_negative_and_outside_index_ranges(self):
        original=self.a.read_bytes()
        for field,value in ((8,-1),(16,-1),(8,2**63-1),(16,2**63-1),(16,8)):
            with self.subTest(field=field,value=value):
                data=bytearray(original)
                struct.pack_into('<q',data,len(data)-44+field,value)
                self.a.write_bytes(data)
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.incomplete(report, 'index_range_invalid')

    def test_entry_offsets_sizes_and_stored_size_consistency(self):
        original=self.a.read_bytes()
        for field,value,code in ((0,-1,'entry_range_invalid'),(8,-1,'entry_range_invalid'),
                                 (16,-1,'entry_range_invalid'),(0,2**63-1,'entry_range_invalid'),
                                 (16,1,'stored_size_mismatch')):
            with self.subTest(field=field):
                self.a.write_bytes(original)
                self.mutate_record('q',field,value)
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,code)

    def test_encryption_and_unknown_flags_are_refused(self):
        original=self.a.read_bytes()
        for flags in (1,2,128,255):
            with self.subTest(flags=flags):
                self.a.write_bytes(original)
                self.mutate_record('B',48,flags)
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,'unsupported_encryption_or_flags')

    def test_compression_block_count_is_checked_before_allocation(self):
        original=FIXTURE([(NAME,b'toy')],compressed=True)
        for count in (-1,0,1025,2**31-1):
            with self.subTest(count=count):
                self.a.write_bytes(original)
                self.mutate_record('i',48,count)
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,'compression_block_limit')

    def test_invalid_compression_ranges_and_block_sizes(self):
        original=FIXTURE([(NAME,b'toy')],compressed=True)
        for fmt,field,value,code in (('q',52,-1,'compression_range_invalid'),
                                     ('q',60,2**63-1,'compression_range_invalid'),
                                     ('I',69,0,'compression_metadata_invalid')):
            with self.subTest(field=field):
                self.a.write_bytes(original)
                self.mutate_record(fmt,field,value)
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,code)

    def test_overlapping_entry_ranges_are_refused(self):
        data=FIXTURE([('a',b'x'),('b',b'y')])
        first=record_position('a')
        second=first+53+4+len('b')+1
        self.a.write_bytes(change_index(data,lambda index:struct.pack_into('<q',index,second,0)))
        result,report=self.run_tool()
        self.assertEqual(result.returncode,1)
        self.incomplete(report,'overlapping_entry_ranges')

    def test_trailing_index_bytes_are_refused(self):
        self.a.write_bytes(change_index(self.a.read_bytes(),lambda index:index.extend(b'junk')))
        result,report=self.run_tool()
        self.assertEqual(result.returncode,1)
        self.incomplete(report,'trailing_index_bytes')

    def test_string_lengths_terminators_and_embedded_nul(self):
        original=self.a.read_bytes()
        for units in (0,2**31-1,-2**31):
            with self.subTest(units=units):
                self.a.write_bytes(change_index(original,lambda index:struct.pack_into('<i',index,0,units)))
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,'unsupported_string_length')
        self.a.write_bytes(change_index(original,lambda index:index.__setitem__(4+len(MOUNT),ord('x'))))
        unused,report=self.run_tool()
        self.incomplete(report,'unterminated_string')
        self.a.write_bytes(change_index(original,lambda index:index.__setitem__(4,0)))
        unused,report=self.run_tool()
        self.incomplete(report,'embedded_string_nul')

    def test_negative_impossible_or_excess_entry_counts(self):
        original=self.a.read_bytes()
        pos=4+len(MOUNT)+1
        for count,code in ((-1,'entry_count_limit'),(50001,'entry_count_limit'),(100,'truncated_index')):
            with self.subTest(count=count):
                self.a.write_bytes(change_index(original,lambda index:struct.pack_into('<i',index,pos,count)))
                result,report=self.run_tool()
                self.assertEqual(result.returncode,1)
                self.incomplete(report,code)

    def test_cli_caps_trigger_actual_guards(self):
        size=footer(self.a.read_bytes())[3]
        for options,code in ((('--max-archive-bytes',44),'archive_size_limit'),
                              (('--max-index-bytes',size-1),'index_byte_limit'),
                              (('--max-total-index-bytes',size-1),'total_index_byte_limit'),
                              (('--max-paks',1),'pak_count_limit'),
                              (('--max-entries',1),'entry_count_limit')):
            with self.subTest(options=options):
                result,report=self.run_tool(*options,selected=[('base',self.a),('mod',self.b)])
                self.assertEqual(result.returncode,1)
                self.incomplete(report,code)

    def test_conflict_limit_clears_all_partial_results(self):
        data=FIXTURE([('a',b'x'),('b',b'y')])
        self.a.write_bytes(data); self.b.write_bytes(data)
        result,report=self.run_tool('--max-conflicts',1,selected=[('base',self.a),('mod',self.b)])
        self.assertEqual(result.returncode,1)
        self.incomplete(report,'conflict_count_limit')

    def test_metadata_budget_is_enforced(self):
        module=runpy.run_path(str(SCRIPT))
        globals_=module['Budget'].charge.__globals__
        globals_['METADATA_LIMIT']=300
        report,unused=module['inspect'](module['parser']().parse_args(['--pak','toy='+str(self.a)]))
        self.incomplete(report,'metadata_byte_limit')

    def test_real_encoded_report_ceiling_returns_incomplete(self):
        prefix='Toy/'+'/'.join(letter*230 for letter in 'abcd')+'/'
        self.a.write_bytes(FIXTURE([(prefix+str(n)+'.txt',b'') for n in range(4500)]))
        result,report=self.run_tool()
        self.assertEqual(result.returncode,1)
        self.incomplete(report,'report_byte_limit')

    def test_duplicate_paths_and_hardlinked_inputs_are_not_self_conflicts(self):
        result,report=self.run_tool(selected=[('base',self.a),('again',self.a)])
        self.assertEqual(result.returncode,1)
        self.incomplete(report,'repeated_archive')

    def test_hardlink_alias_is_refused_when_available(self):
        link=self.root/'alias.pak'
        try:
            link.hardlink_to(self.a)
        except (OSError,NotImplementedError):
            self.skipTest('Hardlink fixture unavailable')
        unused,report=self.run_tool(selected=[('base',self.a),('alias',link)])
        self.incomplete(report,'repeated_archive')

    def test_invalid_and_case_colliding_labels_are_refused(self):
        for labels in (('a','A'),('private name','b'),('x'*65,'b')):
            with self.subTest(labels=labels):
                result,report=self.run_tool(selected=[(labels[0],self.a),(labels[1],self.b)])
                self.assertEqual(result.returncode,1)
                self.incomplete(report,'invalid_or_duplicate_label')

    def test_new_output_and_existing_outputs_inputs_preserved(self):
        output=self.root/'new.json'
        before=self.a.read_bytes()
        result,report=self.run_tool('--output',output)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'')
        saved=output.read_bytes()
        for target in (output,self.a):
            with self.subTest(target=target.name):
                result,report=self.run_tool('--output',target)
                self.assertEqual(result.returncode,1)
                self.assertFalse(report['complete'])
        self.assertEqual(output.read_bytes(),saved)
        self.assertEqual(self.a.read_bytes(),before)

    def test_missing_directory_and_network_inputs_refused(self):
        for path in (self.root/'missing.pak',self.root,Path('//invalid-host/share/file.pak')):
            with self.subTest(path=str(path)):
                result,report=self.run_tool(selected=[('toy',path)])
                self.assertEqual(result.returncode,1)
                self.assertFalse(report['complete'])

    def test_input_mutation_during_read_is_incomplete(self):
        module=runpy.run_path(str(SCRIPT))
        globals_=module['inspect_pak'].__globals__
        original=globals_['region']
        def changed(stream,offset,size):
            data=original(stream,offset,size)
            self.a.write_bytes(self.a.read_bytes()+b'changed by fixture')
            globals_['region']=original
            return data
        globals_['region']=changed
        report,unused=module['inspect'](module['parser']().parse_args(['--pak','toy='+str(self.a)]))
        self.incomplete(report,'input_changed')

    def test_report_is_deterministic_and_argument_order_is_not_priority(self):
        first,report=self.run_tool(selected=[('mod',self.b),('base',self.a)])
        second,unused=self.run_tool(selected=[('base',self.a),('mod',self.b)])
        self.assertEqual(first.stdout,second.stdout)
        self.assertEqual([pak['label'] for pak in report['paks']],['base','mod'])

    def test_bad_cap_arguments_fail_without_native_error(self):
        for flag,value in (('--max-paks','0'),('--max-entries','200001'),('--max-index-bytes','bad'),('--max-paks','9'*5000)):
            with self.subTest(flag=flag):
                result,report=self.run_tool(flag,value)
                self.assertEqual(result.returncode,1)
                self.incomplete(report,'invalid_arguments')

    def test_symlink_input_refused_when_available(self):
        link=self.root/'linked.pak'
        try:
            link.symlink_to(self.a)
        except (OSError,NotImplementedError):
            self.skipTest('File symlink fixture unavailable')
        unused,report=self.run_tool(selected=[('toy',link)])
        self.incomplete(report,'linked_path')

    @unittest.skipUnless(os.name=='nt','Windows junction fixture')
    def test_junction_ancestor_refused_when_available(self):
        target=self.root/'target'; target.mkdir()
        (target/'a.pak').write_bytes(self.a.read_bytes())
        link=self.root/'junction'
        escaped_link=str(link).replace("'","''")
        escaped_target=str(target).replace("'","''")
        created=subprocess.run(['powershell','-NoProfile','-Command',f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],capture_output=True,text=True,timeout=20)
        if created.returncode:
            self.skipTest('Junction fixture unavailable')
        try:
            unused,report=self.run_tool(selected=[('toy',link/'a.pak')])
            self.incomplete(report,'linked_path')
            self.assertEqual((target/'a.pak').read_bytes(),self.a.read_bytes())
        finally:
            self.assertTrue(link.lstat().st_file_attributes & 0x400)
            link.rmdir()  # Only the verified generated junction; never recurse into target.

    def test_generated_examples_and_exclusive_destination(self):
        demo=self.root/'demo'
        command=[sys.executable,'-B',str(GENERATOR),'--destination',str(demo)]
        created=subprocess.run(command,capture_output=True,text=True,timeout=20)
        self.assertEqual(created.returncode,0,created.stderr)
        before={path.name:path.read_bytes() for path in demo.iterdir()}
        result,report=self.run_tool(selected=[('base',demo/'base.pak'),('mod',demo/'mod.pak')])
        self.assertEqual(result.returncode,2)
        self.assertEqual(report['summary']['path_overlaps'],1)
        result,report=self.run_tool(selected=[('base',demo/'base.pak'),('clean',demo/'clean.pak')])
        self.assertEqual(result.returncode,0)
        repeated=subprocess.run(command,capture_output=True,text=True,timeout=20)
        self.assertNotEqual(repeated.returncode,0)
        self.assertEqual(before,{path.name:path.read_bytes() for path in demo.iterdir()})


if __name__=='__main__':
    unittest.main()
