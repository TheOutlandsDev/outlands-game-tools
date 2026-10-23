"""Black-box literal INI/LTX comparisons using original generated text. MIT."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'config_value_diff.py'
EXAMPLE = SCRIPT.parent / 'examples' / 'create_example.py'


class ConfigValueDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix='config-value-diff-')
        self.root = Path(self.temporary.name)
        self.before = self.root / 'before.ini'
        self.after = self.root / 'after.ini'

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, before: str | bytes, after: str | bytes | None = None) -> None:
        after = before if after is None else after
        self.before.write_bytes(before.encode('utf-8') if isinstance(before, str) else before)
        self.after.write_bytes(after.encode('utf-8') if isinstance(after, str) else after)

    def run_tool(self, *extra: object, dialect: str = 'ini', before: Path | None = None,
                 after: Path | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [str(item) for item in extra]
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--before',
                                 str(self.before if before is None else before), '--after',
                                 str(self.after if after is None else after), '--dialect', dialect,
                                 *arguments], capture_output=True, text=True, timeout=30)
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

    def compare(self, before: str | bytes, after: str | bytes, expected: int,
                *extra: object, dialect: str = 'ini') -> dict:
        self.write(before, after)
        result, report = self.run_tool(*extra, dialect=dialect)
        self.assertEqual(result.returncode, expected, report)
        self.assertEqual(report['complete'], expected != 1)
        return report

    def assert_failure(self, report: dict, code: str) -> None:
        self.assertFalse(report['complete'])
        self.assertIn(code, {row['code'] for row in report['errors']})
        self.assertEqual(report['section_changes'], [])
        self.assertEqual(report['value_changes'], [])

    def value(self, report: dict, key: str) -> dict:
        return next(row for row in report['value_changes'] if row['key'] == key)

    def test_empty_files_and_same_input_are_valid(self) -> None:
        self.compare('', '', 0)
        self.write('[toy]\nx = value\n')
        result, report = self.run_tool(after=self.before)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['summary']['keys_unchanged'], 1)

    def test_changed_added_removed_and_unchanged_keys(self) -> None:
        report = self.compare('[toy]\nchanged = old\nremoved = gone\nsame = same\n',
                              '[toy]\nchanged = new\nadded = fresh\nsame = same\n', 2)
        self.assertEqual(report['summary'], {'sections_added': 0, 'sections_removed': 0,
                                           'parents_changed': 0, 'keys_added': 1,
                                           'keys_removed': 1, 'keys_changed': 1, 'keys_unchanged': 1})
        self.assertEqual(self.value(report, 'changed')['kind'], 'changed')
        self.assertEqual(self.value(report, 'added')['kind'], 'added')
        self.assertEqual(self.value(report, 'removed')['kind'], 'removed')

    def test_empty_value_is_distinct_from_absent_key(self) -> None:
        report = self.compare('[toy]\nblank =\n', '[toy]\n', 2)
        change = self.value(report, 'blank')
        self.assertEqual(change['kind'], 'removed')
        self.assertEqual(change['before']['characters'], 0)
        self.assertEqual(change['before']['sha256'], hashlib.sha256(b'').hexdigest())
        self.assertIsNone(change['after'])

    def test_added_removed_sections_include_their_key_rows(self) -> None:
        report = self.compare('[old]\nx = old\n', '[new]\ny = new\n', 2)
        self.assertEqual(report['summary']['sections_added'], 1)
        self.assertEqual(report['summary']['sections_removed'], 1)
        self.assertEqual(report['summary']['keys_added'], 1)
        self.assertEqual(report['summary']['keys_removed'], 1)
        self.assertEqual({row['kind'] for row in report['section_changes']}, {'added', 'removed'})

    def test_empty_section_presence_is_a_difference(self) -> None:
        report = self.compare('', '[empty]\n', 2)
        self.assertEqual(report['summary']['sections_added'], 1)
        self.assertEqual(report['value_changes'], [])

    def test_ini_globals_and_default_are_ordinary_independent_values(self) -> None:
        report = self.compare('global = old\n[DEFAULT]\nx = old\n[toy]\ny = same\n',
                              'global = new\n[DEFAULT]\nx = new\n[toy]\ny = same\n', 2)
        self.assertEqual(report['summary']['keys_changed'], 2)
        self.assertEqual(report['summary']['keys_unchanged'], 1)
        self.assertIsNone(self.value(report, 'global')['section'])
        self.assertEqual(self.value(report, 'x')['section'], 'DEFAULT')
        self.assertEqual(report['value_changes'][0]['section'], None)

    def test_ltx_globals_are_unsupported(self) -> None:
        report = self.compare('x = value\n', '[toy]\nx = value\n', 1, dialect='ltx')
        self.assert_failure(report, 'global_assignment_not_supported')

    def test_ltx_parent_order_is_compared_without_effective_merge(self) -> None:
        report = self.compare('[a]\nx = old\n[b]\nx = other\n[toy]:a,b\ny = same\n',
                              '[a]\nx = old\n[b]\nx = other\n[toy]:b,a\ny = same\n', 2, dialect='ltx')
        self.assertEqual(report['summary']['parents_changed'], 1)
        self.assertEqual(report['summary']['keys_changed'], 0)
        row = report['section_changes'][0]
        self.assertEqual(row['kind'], 'parents_changed')
        self.assertEqual(row['before']['parents'], ['a', 'b'])
        self.assertEqual(row['after']['parents'], ['b', 'a'])

    def test_ltx_duplicate_parent_tokens_are_literal_context(self) -> None:
        self.compare('[toy]:missing,missing\nx = value\n', '[toy]:missing,missing\nx = value\n', 0, dialect='ltx')

    def test_ini_rejects_ltx_parent_header(self) -> None:
        report = self.compare('[toy]:parent\nx = value\n', '[toy]\nx = value\n', 1)
        self.assert_failure(report, 'unsupported_header')

    def test_case_sensitive_is_default_and_insensitive_is_explicit(self) -> None:
        report = self.compare('[Toy]\nKey = same\n', '[toy]\nkey = same\n', 2)
        self.assertEqual(report['summary']['sections_added'], 1)
        self.assertEqual(report['summary']['sections_removed'], 1)
        self.compare('[Toy]\nKey = same\n', '[toy]\nkey = same\n', 0, '--case', 'insensitive')

    def test_sensitive_case_aliases_are_distinct_within_one_file(self) -> None:
        text = '[A]\nKey = first\nkey = second\n[a]\nx = third\n'
        report = self.compare(text, text, 0)
        self.assertEqual(report['summary']['keys_unchanged'], 3)
        report = self.compare(text, text, 1, '--case', 'insensitive')
        self.assertIn(report['errors'][0]['code'], ('duplicate_key', 'duplicate_section'))

    def test_reopened_sections_are_rejected_even_with_last_key_policy(self) -> None:
        text = '[toy]\nx = first\n[toy]\ny = second\n'
        report = self.compare(text, text, 1, '--duplicate-keys', 'last')
        self.assert_failure(report, 'duplicate_section')

    def test_duplicate_keys_rejected_or_last_assignment_used_explicitly(self) -> None:
        before = '[toy]\nx = first\nx = second\n'
        after = '[toy]\nx = third\n'
        report = self.compare(before, after, 1)
        self.assert_failure(report, 'duplicate_key')
        report = self.compare(before, after, 2, '--duplicate-keys', 'last', '--include-values')
        self.assertEqual(self.value(report, 'x')['before']['value'], 'second')
        self.assertEqual(self.value(report, 'x')['before']['line'], 3)
        self.assertEqual(report['inputs']['before']['duplicate_assignments'], 1)

    def test_insensitive_duplicate_keys_follow_selected_duplicate_policy(self) -> None:
        before = '[toy]\nKey = first\nkey = second\n'
        after = '[TOY]\nKEY = second\n'
        report = self.compare(before, after, 1, '--case', 'insensitive')
        self.assert_failure(report, 'duplicate_key')
        self.compare(before, after, 0, '--case', 'insensitive', '--duplicate-keys', 'last')

    def test_literal_values_are_not_coerced_interpolated_or_unquoted(self) -> None:
        report = self.compare('[toy]\nnumber = 01\nboolean = TRUE\nquoted = "value"\nexpr = ${toy}=%NAME%\n',
                              '[toy]\nnumber = 1\nboolean = true\nquoted = value\nexpr = ${other}=%NAME%\n',
                              2, '--include-values')
        self.assertEqual(report['summary']['keys_changed'], 4)
        self.assertEqual(self.value(report, 'quoted')['before']['value'], '"value"')
        self.assertEqual(self.value(report, 'expr')['before']['value'], '${toy}=%NAME%')

    def test_assignment_splits_first_equals_and_trims_only_ascii_edges(self) -> None:
        self.compare('[toy]\n x \t= \ta=b=c \t\n', '[toy]\nx=a=b=c\n', 0)
        report = self.compare('[toy]\nx=value\u00a0\n', '[toy]\nx=value\n', 2, '--include-values')
        self.assertEqual(self.value(report, 'x')['before']['value'], 'value\u00a0')

    def test_default_inline_comment_policy_depends_on_explicit_dialect(self) -> None:
        before = '[toy]\nx = value ; old comment\n'
        after = '[toy]\nx = value ; new comment\n'
        report = self.compare(before, after, 2)
        self.assertEqual(report['policy']['inline_comments'], 'none')
        report = self.compare(before, after, 0, dialect='ltx')
        self.assertEqual(report['policy']['inline_comments'], 'semicolon')
        self.compare(before, after, 0, '--inline-comments', 'semicolon')
        self.compare(before, after, 2, '--inline-comments', 'none', dialect='ltx')

    def test_semicolon_comment_quotes_are_literal_balanced_double_quotes(self) -> None:
        self.compare('[toy]\nx = "one;two" ; old\n', '[toy]\nx = "one;two" ; new\n', 0, dialect='ltx')
        self.compare('[toy]\nx = \'one;two\'\n', '[toy]\nx = \'one;three\'\n', 0, dialect='ltx')
        self.compare('[toy]\nx = "tail\\" ; old\n', '[toy]\nx = "tail\\" ; new\n', 0, dialect='ltx')

    def test_unmatched_quotes_only_fail_when_semicolon_parsing_is_enabled(self) -> None:
        text = '[toy]\nx = "unbalanced\n'
        self.compare(text, text, 0)
        report = self.compare(text, text, 1, dialect='ltx')
        self.assertFalse(report['complete'])
        self.assertNotEqual(report['errors'][0]['code'], 'invalid_arguments')

    def test_line_comments_order_and_line_endings_do_not_change_values(self) -> None:
        self.compare('; before\n# ordinary INI comment\n[toy]\nx=one\ny=two\n',
                     '# after\r\n[toy]\r\ny=two\r\nx=one\r\n', 0)

    def test_include_directives_are_rejected_in_both_dialects(self) -> None:
        for directive in ('#include "unselected.ini"', '# INCLUDE "unselected.ini"'):
            for dialect in ('ini', 'ltx'):
                with self.subTest(directive=directive, dialect=dialect):
                    report = self.compare(directive + '\n[toy]\nx=value\n', '[toy]\nx=value\n', 1, dialect=dialect)
                    self.assert_failure(report, 'unsupported_directive')

    def test_hash_comment_rules_and_inline_hash_literal(self) -> None:
        self.compare('# comment\n[toy]\nx = a#b\n', '[toy]\nx = a#b\n', 0, dialect='ltx')
        report = self.compare('#comment\n[toy]\nx=value\n', '[toy]\nx=value\n', 1, dialect='ltx')
        self.assert_failure(report, 'unsupported_directive')
        self.compare('#comment\n[toy]\nx=value\n', '[toy]\nx=value\n', 0)

    def test_bare_lines_continuations_colon_delimiters_and_dltx_are_unsupported(self) -> None:
        inputs = ('[toy]\nx: value\n', '[toy]\nx=value\ncontinued bare text\n',
                  '[toy]\nbare_key\n', '![toy]\nx=value\n')
        for text in inputs:
            with self.subTest(text=text):
                report = self.compare(text, '[toy]\nx=value\n', 1, dialect='ltx')
                self.assertFalse(report['complete'])

    def test_ascii_identifier_subset_and_ini_section_spaces(self) -> None:
        self.compare('[toy settings]\n$key:part = value\n', '[toy settings]\n$key:part = value\n', 0)
        self.compare('[toy settings]\nx=value\n', '[toy]\nx=value\n', 1, dialect='ltx')
        self.compare('[toy]\nnon ascii \u00e9=value\n', '[toy]\nx=value\n', 1)

    def test_control_characters_are_rejected_even_in_comments(self) -> None:
        for control in ('\x00', '\x1b', '\x7f', '\x85'):
            with self.subTest(control=repr(control)):
                report = self.compare('; comment ' + control + '\n[toy]\nx=value\n', '[toy]\nx=value\n', 1)
                self.assert_failure(report, 'unsupported_control_character')

    def test_unicode_paragraph_separators_remain_inside_literal_values(self) -> None:
        report = self.compare('[toy]\nx=one\u2028two\u2029three\n', '[toy]\nx=other\n', 2, '--include-values')
        self.assertEqual(self.value(report, 'x')['before']['value'], 'one\u2028two\u2029three')

    def test_utf8_bom_and_independent_cp1251_decoding(self) -> None:
        text = '[toy]\nx = \u041f\u0440\u0438\u043c\u0435\u0440\n'
        self.compare(b'\xef\xbb\xbf' + text.encode('utf-8'), text.encode('utf-8'), 0)
        self.compare(text.encode('cp1251'), text.encode('utf-8'), 0, '--before-encoding', 'cp1251')
        report = self.compare(text.encode('cp1251'), text.encode('utf-8'), 1)
        self.assert_failure(report, 'unsupported_encoding')

    def test_utf16_requires_bom_and_can_match_utf8_values(self) -> None:
        text = '[toy]\nx = value\n'
        for data in (text.encode('utf-16'), b'\xfe\xff' + text.encode('utf-16-be')):
            with self.subTest(bom=data[:2]):
                self.compare(data, text.encode('utf-8'), 0, '--before-encoding', 'utf-16')
        for encoding in ('utf-16-le', 'utf-16-be'):
            with self.subTest(encoding=encoding):
                report = self.compare(text.encode(encoding), text.encode('utf-8'), 1, '--before-encoding', 'utf-16')
                self.assert_failure(report, 'utf16_bom_required')

    def test_source_errors_locate_side_and_line_without_source_text(self) -> None:
        for side in ('before', 'after'):
            with self.subTest(side=side):
                good = '[toy]\nx=value\n'
                bad = good + 'bare_private_value_marker\n'
                report = self.compare(bad if side == 'before' else good,
                                      bad if side == 'after' else good, 1)
                self.assertEqual(report['errors'], [{'code': 'unsupported_assignment',
                                                     'side': side, 'line': 3}])
                self.assertNotIn('bare_private_value_marker', json.dumps(report))

    def test_ltx_parent_count_is_bounded_before_retaining_list(self) -> None:
        report = self.compare('[toy]:' + ','.join(['parent'] * 257) + '\n',
                              '[toy]\n', 1, dialect='ltx')
        self.assert_failure(report, 'parent_count_limit')
        self.assertEqual(report['errors'][0]['line'], 1)

    def test_parent_metadata_is_charged_per_item(self) -> None:
        self.write('[toy]:' + ','.join(['aa'] * 100) + '\n')
        bootstrap = '''
import json, runpy, sys
from pathlib import Path
module = runpy.run_path(sys.argv[1])
module['Budget'].charge.__globals__['METADATA_LIMIT'] = 4096
args = module['parser']().parse_args(['--before', sys.argv[2], '--after', sys.argv[3], '--dialect', 'ltx'])
report, unused = module['compare'](args)
print(json.dumps(report))
'''
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT),
                                 str(self.before), str(self.after)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_failure(json.loads(result.stdout), 'metadata_byte_limit')

    def test_default_value_privacy_and_explicit_disclosure(self) -> None:
        before = '[toy]\nx = private-original-before-marker\n'
        after = '[toy]\nx = private-original-after-marker\n'
        self.write(before, after)
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('private-original-before-marker', result.stdout)
        self.assertNotIn('private-original-after-marker', result.stdout)
        descriptor = self.value(report, 'x')['before']
        self.assertEqual(descriptor['characters'], len('private-original-before-marker'))
        self.assertEqual(descriptor['sha256'], hashlib.sha256(b'private-original-before-marker').hexdigest())
        result, report = self.run_tool('--include-values')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.value(report, 'x')['after']['value'], 'private-original-after-marker')

    def test_input_fingerprints_cover_original_bytes_and_source_is_unchanged(self) -> None:
        self.write('[toy]\nx=old\n', '[toy]\nx=new\n')
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})
        for side, path in (('before', self.before), ('after', self.after)):
            self.assertEqual(report['inputs'][side]['bytes'], path.stat().st_size)
            self.assertEqual(report['inputs'][side]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(report['inputs'][side]['sections'], 1)
            self.assertEqual(report['inputs'][side]['keys'], 1)

    def test_invalid_after_file_produces_no_partial_difference_claim(self) -> None:
        report = self.compare('[old]\nx=value\n', '[new]\ny=other\n#include "outside.ini"\n', 1)
        self.assert_failure(report, 'unsupported_directive')

    def test_report_is_deterministic(self) -> None:
        self.write('[toy]\nx=old\n', '[toy]\nx=new\n')
        first, _ = self.run_tool()
        second, _ = self.run_tool()
        self.assertEqual(first.stdout, second.stdout)

    def test_existing_output_and_inputs_are_never_overwritten(self) -> None:
        self.write('[toy]\nx=value\n')
        output = self.root / 'existing.json'
        output.write_bytes(b'keep original toy output')
        for target in (output, self.before, self.after):
            with self.subTest(target=target.name):
                saved = target.read_bytes()
                result, report = self.run_tool('--output', target)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])
                self.assertEqual(target.read_bytes(), saved)

    def test_new_output_beside_inputs_is_valid_json(self) -> None:
        self.write('[toy]\nx=old\n', '[toy]\nx=new\n')
        output = self.root / 'new-report.json'
        result, report = self.run_tool('--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)

    def test_missing_or_directory_input_fails_without_path_disclosure(self) -> None:
        self.write('[toy]\nx=value\n')
        for path in (self.root / 'unselected-personal-file.ini', self.root):
            with self.subTest(path=path.name):
                result, report = self.run_tool(before=path)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])

    def test_resource_caps_use_actual_controlled_guard_codes(self) -> None:
        self.write('[toy]\nx=one\nx=two\n')
        for options, code in ((('--max-file-bytes', 1), 'input_byte_limit'),
                              (('--max-lines', 1), 'line_count_limit'),
                              (('--max-records', 2, '--duplicate-keys', 'last'), 'record_count_limit')):
            with self.subTest(options=options):
                result, report = self.run_tool(*options)
                self.assertEqual(result.returncode, 1)
                self.assert_failure(report, code)
        self.write('', '[new]\nx=value\n')
        result, report = self.run_tool('--max-changes', 1)
        self.assertEqual(result.returncode, 1)
        self.assert_failure(report, 'change_count_limit')

    def test_fixed_line_character_limit_applies_even_to_comment(self) -> None:
        report = self.compare(';' + 'a' * 65536 + '\n', '', 1)
        self.assert_failure(report, 'line_character_limit')

    def test_encoded_report_cap_is_incomplete_not_truncated_success(self) -> None:
        before = '[toy]\n' + ''.join(f'k{number}= ' + 'a' * 36000 + '\n' for number in range(120))
        after = '[toy]\n' + ''.join(f'k{number}= ' + 'b' * 36000 + '\n' for number in range(120))
        report = self.compare(before, after, 1, '--max-file-bytes', 16 * 1024 * 1024, '--include-values')
        self.assert_failure(report, 'report_byte_limit')

    def test_invalid_or_above_ceiling_arguments_fail_cleanly(self) -> None:
        self.write('[toy]\nx=value\n')
        for option, value in (('--max-lines', '0'), ('--max-records', '200001'),
                              ('--max-file-bytes', str(16 * 1024 * 1024 + 1)),
                              ('--max-changes', 'not-a-number'), ('--max-lines', '9' * 500)):
            with self.subTest(option=option):
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--before', str(self.before),
                                         '--after', str(self.after), '--dialect', 'ini', option, value],
                                        capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)

    def test_observed_input_change_prevents_complete_comparison(self) -> None:
        self.write('[toy]\nx=value\n')
        bootstrap = '''
import os, runpy, sys
from pathlib import Path
original = os.fstat
target = Path(sys.argv[2])
def changed(fd):
    info = original(fd)
    os.fstat = original
    target.write_bytes(b'[changed_toy]\\nx=other\\n')
    return info
os.fstat = changed
sys.argv = [sys.argv[1], '--before', sys.argv[2], '--after', sys.argv[3], '--dialect', 'ini']
runpy.run_path(sys.argv[0], run_name='__main__')
'''
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT),
                                 str(self.before), str(self.after)], capture_output=True, text=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['complete'])

    def test_symlink_input_is_refused(self) -> None:
        self.write('[toy]\nx=value\n')
        link = self.root / 'linked.ini'
        try:
            link.symlink_to(self.before)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'File symlinks unavailable: {type(error).__name__}')
        result, report = self.run_tool(before=link)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction/reparse-point behavior')
    def test_junction_ancestor_is_refused(self) -> None:
        self.write('[toy]\nx=value\n')
        target = self.root / 'target'
        target.mkdir()
        (target / 'before.ini').write_bytes(self.before.read_bytes())
        link = self.root / 'junction'
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        created = subprocess.run(['powershell', '-NoProfile', '-Command',
                                  f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
                                 capture_output=True, text=True, timeout=20)
        if created.returncode:
            self.skipTest('Creating a Windows junction is unavailable')
        try:
            result, report = self.run_tool(before=link / 'before.ini')
            self.assertEqual(result.returncode, 1)
            self.assertFalse(report['complete'])
            self.assertEqual((target / 'before.ini').read_bytes(), self.before.read_bytes())
        finally:
            info = link.lstat()
            self.assertTrue(getattr(info, 'st_file_attributes', 0) & 0x400)
            link.rmdir()  # Remove only this generated junction, never recurse into target.

    def test_original_generated_examples_and_exclusive_destination(self) -> None:
        destination = self.root / 'example'
        created = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(created.returncode, 0, created.stderr)
        for dialect in ('ini', 'ltx'):
            result, report = self.run_tool(before=destination / ('before.' + dialect),
                                           after=destination / ('after.' + dialect), dialect=dialect)
            self.assertEqual(result.returncode, 2)
            if dialect == 'ini':
                self.assertEqual(report['summary'], {'sections_added': 0, 'sections_removed': 0,
                                                     'parents_changed': 0, 'keys_added': 1,
                                                     'keys_removed': 2, 'keys_changed': 2, 'keys_unchanged': 3})
            else:
                self.assertEqual(report['summary'], {'sections_added': 0, 'sections_removed': 0,
                                                     'parents_changed': 1, 'keys_added': 1,
                                                     'keys_removed': 1, 'keys_changed': 1, 'keys_unchanged': 4})
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        repeated = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                                  capture_output=True, text=True, timeout=20)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(before, {path.name: path.read_bytes() for path in destination.iterdir()})


if __name__ == '__main__':
    unittest.main()
