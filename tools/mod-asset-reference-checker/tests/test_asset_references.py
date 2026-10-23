"""Black-box checks with original generated LTX, index and placeholder data. MIT."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'asset_references.py'
EXAMPLE = SCRIPT.parent / 'examples' / 'create_example.py'


class AssetReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix='asset-reference-test-')
        self.root = Path(self.temporary.name)
        self.assets = self.root / 'gamedata'
        self.configs = self.assets / 'configs'
        self.configs.mkdir(parents=True)
        self.entry = 'toy.ltx'

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def config(self, text: str | bytes, name: str = 'toy.ltx') -> Path:
        path = self.configs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8') if isinstance(text, str) else text)
        return path

    def asset(self, relative: str = 'meshes/toy/present.ogf', data: bytes = b'Original toy placeholder, not a valid game format.\n') -> Path:
        path = self.assets / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def index(self, paths: list[str], *, name: str = 'index.json') -> Path:
        path = self.root / name
        path.write_text(json.dumps({'schema_version': 1, 'kind': 'asset-path-index', 'paths': paths}), encoding='utf-8')
        return path

    def run_tool(self, *extra: object, entries: tuple[str, ...] | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [str(value) for value in extra]
        command = [sys.executable, '-B', str(SCRIPT), '--config-root', str(self.configs),
                   '--asset-root', str(self.assets)]
        for entry in (self.entry,) if entries is None else entries:
            command.extend(('--entry', entry))
        result = subprocess.run([*command, *arguments], capture_output=True, text=True, timeout=30)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn(str(self.root), result.stderr)
        payload = result.stdout
        if not payload.strip() and '--output' in arguments:
            output = Path(arguments[arguments.index('--output') + 1])
            if output.is_file():
                payload = output.read_text(encoding='utf-8')
        self.assertTrue(payload.strip(), result.stderr)
        self.assertNotIn(str(self.root), payload)
        return result, json.loads(payload)

    def one_reference(self, report: dict) -> dict:
        self.assertEqual(len(report['references']), 1, report)
        return report['references'][0]

    def snapshot(self) -> dict[str, str]:
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob('*') if path.is_file()}

    def test_extensionless_visual_resolves_loose_placeholder(self) -> None:
        self.config('[toy]\nvisual = toy\\present\n')
        path = self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report['complete'])
        reference = self.one_reference(report)
        self.assertEqual(reference['kind'], 'file')
        self.assertEqual(reference['status'], 'found_loose')
        self.assertEqual(reference['target'], 'meshes/toy/present.ogf')
        self.assertEqual(reference['loose_file'], {'path': 'meshes/toy/present.ogf', 'bytes': path.stat().st_size})

    def test_explicit_extension_is_not_appended_twice(self) -> None:
        self.config('[toy]\nvisual = toy/present.ogf\n')
        self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.one_reference(report)['target'], 'meshes/toy/present.ogf')

    def test_rule_prefix_is_explicit_not_heuristically_stripped(self) -> None:
        self.config('[toy]\nvisual = meshes/toy/present\n')
        self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.one_reference(report)['target'], 'meshes/meshes/toy/present.ogf')

    def test_different_explicit_extension_is_unsupported(self) -> None:
        self.config('[toy]\nvisual = toy/present.dds\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_empty_asset_file_is_present_without_format_validation(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        self.asset(data=b'')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.one_reference(report)['loose_file']['bytes'], 0)

    def test_absence_is_coverage_unknown_by_default(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report['complete'])
        reference = self.one_reference(report)
        self.assertEqual(reference['status'], 'unresolved_coverage')
        self.assertIsNone(reference['loose_file'])
        self.assertEqual(report['summary']['missing_in_declared_coverage'], 0)

    def test_complete_assets_attestation_changes_only_absence_classification(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        result, report = self.run_tool('--assume-complete-assets')
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report['complete'])
        self.assertEqual(self.one_reference(report)['status'], 'missing_in_declared_coverage')
        self.assertTrue(report['policy']['assume_complete_assets'])

    def test_index_listing_is_not_reported_as_verified_loose_payload(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        index = self.index(['meshes/toy/absent.ogf'])
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 0)
        reference = self.one_reference(report)
        self.assertEqual(reference['status'], 'listed_in_index')
        self.assertIsNone(reference['loose_file'])
        self.assertEqual(report['inputs']['index']['paths'], 1)

    def test_partial_index_does_not_make_unlisted_path_confirmed_missing(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        index = self.index(['meshes/toy/another.ogf'])
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.one_reference(report)['status'], 'unresolved_coverage')

    def test_selected_section_declaration_resolves_ammo_reference(self) -> None:
        self.config('[toy_weapon]\nammo_class = ammo_toy\n[ammo_toy]\nvalue = original\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        reference = self.one_reference(report)
        self.assertEqual(reference['kind'], 'section')
        self.assertEqual(reference['status'], 'declared_in_selection')
        self.assertEqual(reference['target'], 'ammo_toy')

    def test_literal_section_lists_are_split_into_independent_references(self) -> None:
        self.config('[toy_weapon]\nammo_class = ammo_one, ammo_two\n[ammo_one]\n[ammo_two]\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual([row['target'] for row in report['references']], ['ammo_one', 'ammo_two'])
        self.assertEqual(report['summary']['section_references'], 2)

    def test_section_presence_does_not_expand_inheritance(self) -> None:
        self.config('[base]\nvisual = toy/present\n[child]:base\n')
        self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['file_references'], 1)
        child = next(section for section in report['context']['sections'] if section['name'] == 'child')
        self.assertEqual(child['parents'], ['base'])

    def test_undeclared_section_is_unknown_without_attestation(self) -> None:
        self.config('[toy_weapon]\nammo_class = ammo_absent\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.one_reference(report)['status'], 'unresolved_coverage')
        result, report = self.run_tool('--assume-complete-sections')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.one_reference(report)['status'], 'missing_in_declared_coverage')

    def test_asset_and_section_attestations_are_independent(self) -> None:
        self.config('[toy]\nvisual = toy/absent\nammo_class = ammo_absent\n')
        result, report = self.run_tool('--assume-complete-assets')
        self.assertEqual(result.returncode, 2)
        by_kind = {row['kind']: row for row in report['references']}
        self.assertEqual(by_kind['file']['status'], 'missing_in_declared_coverage')
        self.assertEqual(by_kind['section']['status'], 'unresolved_coverage')

    def test_custom_file_rule_replaces_visual_default(self) -> None:
        self.config('[toy]\nvisual = absent/default\nicons_texture = toy/icon\n')
        self.asset('textures/toy/icon.dds')
        result, report = self.run_tool('--file-rule', 'icons_texture=textures:.dds')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.one_reference(report)['key'], 'icons_texture')
        self.assertEqual(self.one_reference(report)['target'], 'textures/toy/icon.dds')

    def test_custom_section_key_replaces_ammo_default(self) -> None:
        self.config('[toy]\nammo_class = absent_default\nrequires = available\n[available]\n')
        result, report = self.run_tool('--section-key', 'requires')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.one_reference(report)['key'], 'requires')

    def test_unconfigured_keys_and_nonreference_values_are_not_disclosed(self) -> None:
        self.config('[toy]\nprivate_note = unshared-original-text-never-echo\nVisual = also_unconfigured\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertFalse(report['references'])
        self.assertNotIn('unshared-original-text-never-echo', result.stdout)
        self.assertNotIn('also_unconfigured', result.stdout)

    def test_blank_selected_value_is_informational(self) -> None:
        self.config('[toy]\nvisual = \n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        reference = self.one_reference(report)
        self.assertEqual(reference['status'], 'empty_reference')
        self.assertIsNone(reference['target'])
        self.assertEqual(report['summary']['empty_references'], 1)

    def test_literal_include_graph_contributes_section_declarations(self) -> None:
        self.config('#include "parts/ammo.ltx"\n[toy]\nammo_class = ammo_toy\n')
        self.config('[ammo_toy]\n', 'parts/ammo.ltx')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['config_files'], 2)
        self.assertEqual(self.one_reference(report)['status'], 'declared_in_selection')
        self.assertEqual(len(report['context']['includes']), 1)

    def test_nested_include_parent_step_can_stay_inside_config_root(self) -> None:
        self.config('#include "parts/child.ltx"\n[toy]\nammo_class = ammo_toy\n')
        self.config('#include "../ammo.ltx"\n[child]\n', 'parts/child.ltx')
        self.config('[ammo_toy]\n', 'ammo.ltx')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['config_files'], 3)

    def test_repeated_include_reads_one_config_without_duplicate_section_error(self) -> None:
        self.config('#include "ammo.ltx"\n#include "ammo.ltx"\n[toy]\nammo_class = ammo_toy\n')
        self.config('[ammo_toy]\n', 'ammo.ltx')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['config_files'], 2)
        self.assertEqual(len(report['context']['includes']), 2)

    def test_include_escape_does_not_open_unselected_file(self) -> None:
        self.config('#include "../../unselected-private-marker.ltx"\n[toy]\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.assertNotIn('unselected-private-marker', result.stdout)

    def test_missing_include_and_include_cycle_are_incomplete(self) -> None:
        self.config('#include "missing.ltx"\n[toy]\nvisual = toy/absent\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.config('#include "second.ltx"\n[toy]\n')
        self.config('#include "toy.ltx"\n[second]\n', 'second.ltx')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_duplicate_sections_or_keys_and_dltx_are_incomplete(self) -> None:
        inputs = ('[toy]\nvisual = toy/one\nvisual = toy/two\n', '[toy]\n[toy]\n',
                  '![toy]\nvisual = toy/present\n')
        for text in inputs:
            with self.subTest(text=text):
                self.config(text)
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_unsafe_file_literals_are_not_echoed_as_targets(self) -> None:
        for value in ('../outside', '/rooted/mesh', 'C:\\private-marker\\mesh',
                      'toy/../../outside', 'toy/*.ogf'):
            with self.subTest(value=value):
                self.config('[toy]\nvisual = ' + value + '\n')
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])
                self.assertNotIn('private-marker', result.stdout)

    def test_file_multivalue_or_expression_is_not_silently_guessed(self) -> None:
        for value in ('toy/one,toy/two', '$choose_mesh()', '{toy_condition}toy/one', "'toy/one'"):
            with self.subTest(value=value):
                self.config('[toy]\nvisual = ' + value + '\n')
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_selected_sentinels_and_numbers_are_not_file_or_section_guesses(self) -> None:
        for key, value in (('visual', 'nil'), ('visual', 'false'), ('visual', '123'),
                           ('ammo_class', 'none'), ('ammo_class', '123')):
            with self.subTest(key=key, value=value):
                self.config(f'[toy]\n{key} = {value}\n')
                result, report = self.run_tool()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_quoted_file_literal_comments_and_empty_quotes(self) -> None:
        self.config('; visual = ignored/comment\n[toy]\nvisual = "toy/present" ; trailing comment\n')
        self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['file_references'], 1)
        self.config('[toy]\nvisual = ""\n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.one_reference(report)['status'], 'empty_reference')

    def test_utf8_bom_and_explicit_cp1251_selection(self) -> None:
        text = '[toy]\n; \u041f\u0440\u0438\u043c\u0435\u0440\nvisual = \n'
        self.config(b'\xef\xbb\xbf' + text.encode('utf-8'))
        result, _ = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.config(text.encode('cp1251'))
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        result, report = self.run_tool('--encoding', 'cp1251')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['policy']['encoding'], 'cp1251')

    def test_existing_report_is_not_overwritten(self) -> None:
        self.config('[toy]\n')
        output = self.root / 'existing.json'
        output.write_bytes(b'keep original output')
        result, report = self.run_tool('--output', output)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.assertEqual(output.read_bytes(), b'keep original output')

    def test_report_must_be_outside_both_roots(self) -> None:
        self.config('[toy]\n')
        for output in (self.configs / 'report.json', self.assets / 'report.json'):
            with self.subTest(output=output.name):
                result, report = self.run_tool('--output', output)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])
                self.assertFalse(output.exists())

    def test_new_report_has_valid_json(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        output = self.root / 'new-report.json'
        result, report = self.run_tool('--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)

    def test_relative_entry_guard_and_parent_traversal(self) -> None:
        self.config('[toy]\n')
        for entry in ('../outside.ltx', str(self.configs / 'toy.ltx'), '/absolute.ltx'):
            with self.subTest(entry=entry):
                result, report = self.run_tool(entries=(entry,))
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_strict_index_schema_paths_and_duplicate_keys(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        index = self.root / 'invalid-index.json'
        cases = [
            {'schema_version': True, 'kind': 'asset-path-index', 'paths': []},
            {'schema_version': 1, 'kind': 'other', 'paths': []},
            {'schema_version': 1, 'kind': 'asset-path-index', 'paths': [], 'extra': 'untrusted-private-field'},
            {'schema_version': 1, 'kind': 'asset-path-index', 'paths': ['../outside.ogf']},
            {'schema_version': 1, 'kind': 'asset-path-index', 'paths': ['meshes/A.ogf', 'meshes/a.ogf']},
            {'schema_version': 1, 'kind': 'asset-path-index', 'paths': [42]},
        ]
        for data in cases:
            with self.subTest(data=data):
                index.write_text(json.dumps(data), encoding='utf-8')
                result, report = self.run_tool('--packed-index', index)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])
                self.assertNotIn('untrusted-private-field', result.stdout)
        index.write_text('{"schema_version":1,"schema_version":1,"kind":"asset-path-index","paths":[]}', encoding='utf-8')
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_source_and_placeholder_bytes_are_unchanged(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        self.asset()
        before = self.snapshot()
        result, _ = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_loose_asset_content_is_never_opened(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        target = self.asset(data=b'\x00\xfforiginal invalid-format toy bytes')
        bootstrap = '''
import os, runpy, sys
target = os.path.normcase(os.path.abspath(sys.argv[2]))
def guard(event, arguments):
    if event == 'open' and isinstance(arguments[0], (str, bytes, os.PathLike)):
        if os.path.normcase(os.path.abspath(os.fsdecode(arguments[0]))) == target:
            raise OSError('toy payload read blocked by test')
sys.addaudithook(guard)
sys.argv = [sys.argv[1], '--config-root', sys.argv[3], '--entry', 'toy.ltx', '--asset-root', sys.argv[4]]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT),
                                 str(target), str(self.configs), str(self.assets)],
                                capture_output=True, text=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.one_reference(json.loads(result.stdout))['status'], 'found_loose')

    def test_observed_config_change_prevents_complete_report(self) -> None:
        target = self.config('[toy]\nvisual = \n')
        bootstrap = '''
import os, runpy, sys
from pathlib import Path
original = os.fstat
target = Path(sys.argv[2])
def changed(fd):
    info = original(fd)
    os.fstat = original
    target.write_bytes(b'[changed_toy]\\nvisual = \\n')
    return info
os.fstat = changed
sys.argv = [sys.argv[1], '--config-root', sys.argv[3], '--entry', 'toy.ltx', '--asset-root', sys.argv[4]]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT),
                                 str(target), str(self.configs), str(self.assets)],
                                capture_output=True, text=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(json.loads(result.stdout)['complete'])

    def test_config_fingerprints_match_original_input_bytes(self) -> None:
        path = self.config('[toy]\nvisual = \n')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['inputs']['configs'], [{'path': 'toy.ltx', 'bytes': path.stat().st_size,
                                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}])

    def test_reference_and_directory_entry_limits_are_incomplete(self) -> None:
        self.config('[first]\nvisual = toy/one\n[second]\nvisual = toy/two\n')
        result, report = self.run_tool('--max-references', 1)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.assertIn('reference_count_limit', {error['code'] for error in report['errors']})
        self.config('[toy]\nvisual = toy/present\n')
        self.asset()
        (self.assets / 'another-entry').mkdir()
        result, report = self.run_tool('--max-directory-entries', 1)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_config_file_and_include_depth_limits_are_incomplete(self) -> None:
        self.config('#include "second.ltx"\n[toy]\n')
        self.config('[second]\n', 'second.ltx')
        for option in ('--max-files', '--max-depth'):
            with self.subTest(option=option):
                result, report = self.run_tool(option, 1)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_per_file_and_total_byte_limits_are_incomplete(self) -> None:
        self.config('#include "second.ltx"\n[toy]\n')
        self.config('[second]\n', 'second.ltx')
        for option, value in (('--max-file-bytes', 5), ('--max-total-bytes', 30)):
            with self.subTest(option=option):
                result, report = self.run_tool(option, value)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_invalid_limits_fail_without_traceback(self) -> None:
        self.config('[toy]\n')
        for option, value in (('--max-references', '0'), ('--max-depth', '129'),
                              ('--max-files', '10001'), ('--max-total-bytes', 'not-a-number'),
                              ('--max-file-bytes', '9' * 500)):
            with self.subTest(option=option):
                command = [sys.executable, '-B', str(SCRIPT), '--config-root', str(self.configs),
                           '--entry', self.entry, '--asset-root', str(self.assets), option, value]
                result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)

    def test_oversized_or_excessively_nested_index_is_incomplete(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        index = self.root / 'invalid-index.json'
        with index.open('wb') as stream:
            stream.truncate(8 * 1024 * 1024 + 1)
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        index.write_text('[' * 1500 + '0' + ']' * 1500, encoding='utf-8')
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_deep_distinct_index_branches_obey_metadata_budget(self) -> None:
        self.config('[toy]\nvisual = toy/absent\n')
        paths = [f'n{number}/' + '/'.join(['a'] * 99) + f'/x{number}.ogf'
                 for number in range(2600)]
        index = self.index(paths)
        self.assertLess(index.stat().st_size, 8 * 1024 * 1024)
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.assertIn('metadata_byte_limit', {error['code'] for error in report['errors']})

    def test_conflicting_or_unsafe_rule_arguments_fail_cleanly(self) -> None:
        self.config('[toy]\n')
        cases = (('--file-rule', 'visual=../meshes:.ogf'),
                 ('--file-rule', 'visual=meshes:.ogf', '--section-key', 'visual'),
                 ('--file-rule', 'visual=meshes:.ogf', '--file-rule', 'visual=textures:.dds'))
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--config-root',
                                         str(self.configs), '--entry', self.entry, '--asset-root',
                                         str(self.assets), *arguments], capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)

    def test_file_case_mismatch_is_a_review_finding(self) -> None:
        self.config('[toy]\nvisual = toy/PRESENT\n')
        self.asset()
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        reference = self.one_reference(report)
        self.assertEqual(reference['status'], 'found_loose')
        self.assertTrue(reference['found_case_mismatch'])
        self.assertEqual(report['summary']['case_mismatches'], 1)

    def test_index_case_mismatch_is_a_review_finding(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        index = self.index(['meshes/toy/PRESENT.ogf'])
        result, report = self.run_tool('--packed-index', index)
        self.assertEqual(result.returncode, 2)
        reference = self.one_reference(report)
        self.assertEqual(reference['status'], 'listed_in_index')
        self.assertTrue(reference['found_case_mismatch'])

    @unittest.skipIf(os.name == 'nt', 'Case-sensitive directory fixture')
    def test_case_colliding_loose_assets_are_incomplete(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        self.asset()
        self.asset('meshes/toy/PRESENT.ogf')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    @unittest.skipIf(os.name == 'nt', 'Distinct case-only root directories require a case-sensitive filesystem')
    def test_casefold_equal_but_physically_distinct_roots_are_rejected(self) -> None:
        config_root = self.root / 'selection'
        asset_root = self.root / 'SELECTION'
        config_root.mkdir()
        try:
            asset_root.mkdir()
        except FileExistsError:
            self.skipTest('Filesystem does not support distinct case-only directories')
        (config_root / 'toy.ltx').write_text('[toy]\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--config-root', str(config_root),
                                 '--entry', 'toy.ltx', '--asset-root', str(asset_root)],
                                capture_output=True, text=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report['complete'])
        self.assertIn('ambiguous_case_alias', {error['code'] for error in report['errors']})

    def test_asset_symlink_is_refused(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        target = self.root / 'outside.ogf'
        target.write_bytes(b'unselected original toy target')
        link = self.assets / 'meshes/toy/present.ogf'
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'File symlinks unavailable: {type(error).__name__}')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction/reparse-point behavior')
    def test_asset_junction_ancestor_is_refused(self) -> None:
        self.config('[toy]\nvisual = toy/present\n')
        target = self.root / 'junction-target'
        target.mkdir()
        (target / 'present.ogf').write_bytes(b'original unselected toy placeholder')
        link = self.assets / 'meshes/toy'
        link.parent.mkdir(parents=True)
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        created = subprocess.run(['powershell', '-NoProfile', '-Command',
                                  f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
                                 capture_output=True, text=True, timeout=20)
        if created.returncode:
            self.skipTest('Creating a Windows junction is unavailable')
        try:
            result, report = self.run_tool()
            self.assertEqual(result.returncode, 1)
            self.assertFalse(report['complete'])
            self.assertEqual((target / 'present.ogf').read_bytes(), b'original unselected toy placeholder')
        finally:
            info = link.lstat()
            self.assertTrue(getattr(info, 'st_file_attributes', 0) & 0x400)
            link.rmdir()  # Remove only this generated junction, never recurse into target.

    def test_generated_example_and_exclusive_destination(self) -> None:
        destination = self.root / 'example'
        generated = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                                   capture_output=True, text=True, timeout=20)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        for indexed, expected_exit in ((False, 2), (True, 0)):
            command = [sys.executable, '-B', str(SCRIPT), '--config-root',
                       str(destination / 'gamedata/configs'), '--entry', 'toy.ltx',
                       '--asset-root', str(destination / 'gamedata')]
            if indexed:
                command.extend(('--packed-index', str(destination / 'index.json')))
            compared = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(compared.returncode, expected_exit, compared.stdout)
            report = json.loads(compared.stdout)
            self.assertTrue(report['complete'])
            self.assertEqual(report['summary']['config_files'], 1)
            self.assertEqual(report['summary']['file_references'], 2)
            self.assertEqual(report['summary']['section_references'], 1)
            self.assertEqual(report['summary']['found_loose'], 1)
            self.assertEqual(report['summary']['declared_in_selection'], 1)
            self.assertEqual(report['summary']['unresolved_coverage'], 0 if indexed else 1)
            self.assertEqual(report['summary']['listed_in_index'], 1 if indexed else 0)
        before = {path.relative_to(destination).as_posix(): path.read_bytes()
                  for path in destination.rglob('*') if path.is_file()}
        repeated = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                                  capture_output=True, text=True, timeout=20)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(before, {path.relative_to(destination).as_posix(): path.read_bytes()
                                  for path in destination.rglob('*') if path.is_file()})


if __name__ == '__main__':
    unittest.main()
