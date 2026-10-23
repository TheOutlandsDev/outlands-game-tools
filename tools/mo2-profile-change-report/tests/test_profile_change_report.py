"""Original synthetic saved-profile comparisons; no installed profiles or game files. MIT."""
import importlib.util
import itertools
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

SCRIPT = Path(__file__).resolve().parents[1] / 'profile_change_report.py'
GENERATOR = SCRIPT.parent / 'examples/create_example.py'
spec = importlib.util.spec_from_file_location('profile_change_report', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='profile-report-')
        self.root = Path(self.temp.name)
        self.before, self.after = self.root/'before.txt', self.root/'after.txt'
        self.set_lists('+A\n+B\n-C\n', '+A\n+B\n-C\n')

    def tearDown(self):
        self.temp.cleanup()

    def set_lists(self, left, right):
        self.before.write_bytes(left.encode('utf-8') if isinstance(left, str) else left)
        self.after.write_bytes(right.encode('utf-8') if isinstance(right, str) else right)

    def run_tool(self, *options, before=None, after=None):
        args = [sys.executable, '-B', str(SCRIPT), '--before', str(before or self.before), '--after', str(after or self.after)]
        args.extend(str(value) for value in options)
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        text = result.stdout
        if not text and '--output' in args:
            output = Path(args[args.index('--output')+1])
            if output.is_file():
                text = output.read_text(encoding='utf-8')
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn(str(self.root), text + result.stderr)
        self.assertTrue(text, result.stderr)
        return result.returncode, json.loads(text)

    def incomplete(self, expected):
        status, report = self.run_tool()
        self.assertEqual(status, 1)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['before'])
        self.assertIsNone(report['after'])
        self.assertEqual(report['summary'], {})
        self.assertIn(expected, [row['code'] for row in report['errors']])

    def test_identical_and_source_preservation(self):
        before, after = self.before.read_bytes(), self.after.read_bytes()
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertTrue(report['complete'])
        self.assertTrue(report['input_bytes_equal'])
        self.assertFalse(report['semantic_changes'])
        self.assertEqual((self.before.read_bytes(), self.after.read_bytes()), (before, after))

    def test_added_removed_enabled_disabled(self):
        self.set_lists('+A\n-B\n+Old\n', '-A\n+B\n+New\n')
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        changes = report['changes']['mods']
        self.assertEqual([row['name'] for row in changes['added']], ['New'])
        self.assertEqual([row['name'] for row in changes['removed']], ['Old'])
        self.assertEqual([row['after']['name'] for row in changes['enabled']], ['B'])
        self.assertEqual([row['after']['name'] for row in changes['disabled']], ['A'])
        self.assertEqual(changes['reordered'], [])

    def test_insertion_removal_not_reorder(self):
        self.set_lists('+A\n+Old\n+B\n+C\n', '+New\n+A\n+B\n+New2\n+C\n')
        self.assertEqual(self.run_tool()[1]['changes']['mods']['reordered'], [])

    def test_swap_reports_both_participants(self):
        self.set_lists('+A\n+B\n+C\n', '+B\n+A\n+C\n')
        rows = self.run_tool()[1]['changes']['mods']['reordered']
        self.assertEqual([row['after']['name'] for row in rows], ['B', 'A'])
        self.assertEqual(rows[0]['crossed_with'], 'A')

    def test_same_rank_middle_can_be_reordered(self):
        self.set_lists('+A\n+B\n+C\n', '+C\n+B\n+A\n')
        rows = self.run_tool()[1]['changes']['mods']['reordered']
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['before_common_rank'], rows[1]['after_common_rank'])

    def test_disabled_entries_participate_in_order(self):
        self.set_lists('-A\n-B\n', '-B\n-A\n')
        self.assertEqual(len(self.run_tool()[1]['changes']['mods']['reordered']), 2)

    def test_separator_only_relocation_does_not_reorder_mods(self):
        self.set_lists('-Group_separator\n+A\n+B\n', '+A\n-Group_separator\n+B\n')
        changes = self.run_tool()[1]['changes']
        self.assertEqual(changes['mods']['reordered'], [])
        self.assertEqual(len(changes['separators']['relocated']), 1)
        self.assertEqual(changes['separators']['relocated'][0]['crossed_with'], 'A')

    def test_separator_insertion_does_not_relocate_existing(self):
        self.set_lists('-Group_separator\n+A\n', '-New_separator\n-Group_separator\n+A\n')
        rows = self.run_tool()[1]['changes']['separators']
        self.assertEqual(len(rows['added']), 1)
        self.assertEqual(rows['relocated'], [])

    def test_separator_order_and_marker_are_metadata(self):
        self.set_lists('-One_separator\n-Two_separator\n+A\n', '+Two_separator\n-One_separator\n+A\n')
        changes = self.run_tool()[1]['changes']
        self.assertEqual(len(changes['separators']['reordered']), 2)
        self.assertEqual(len(changes['separators']['marker_changed']), 1)
        self.assertEqual(changes['mods']['enabled'], [])
        self.assertIsNone(changes['separators']['marker_changed'][0]['after']['enabled'])

    def test_foreign_entries_separate_from_regular_enablement(self):
        self.set_lists('*Base\n*Old\n+A\n', '*New\n*Base\n+A\n')
        changes = self.run_tool()[1]['changes']
        self.assertEqual([row['name'] for row in changes['foreign']['added']], ['New'])
        self.assertEqual([row['name'] for row in changes['foreign']['removed']], ['Old'])
        self.assertEqual(changes['mods']['enabled'], [])

    def test_kind_transition_is_group_removal_and_addition(self):
        self.set_lists('*Base\n', '+Base\n')
        changes = self.run_tool()[1]['changes']
        self.assertEqual(len(changes['foreign']['removed']), 1)
        self.assertEqual(len(changes['mods']['added']), 1)
        self.assertEqual(changes['mods']['enabled'], [])

    def test_foreign_separator_refused(self):
        self.set_lists('*Group_separator\n', '')
        self.incomplete('foreign_separator_ambiguous')

    def test_spelling_changes_not_fabricated_rename(self):
        self.set_lists('+Texture\n', '+TEXTURE\n')
        changes = self.run_tool()[1]['changes']['mods']
        self.assertEqual(len(changes['name_spelling_changed']), 1)
        self.assertEqual(changes['added'], [])
        self.set_lists('+Texture\n', '+Different Name\n')
        changes = self.run_tool()[1]['changes']['mods']
        self.assertEqual(len(changes['added']), 1)
        self.assertEqual(len(changes['removed']), 1)

    def test_unicode_casefold_policy(self):
        self.set_lists('+Stra\u00dfe\n', '+STRASSE\n')
        self.assertEqual(len(self.run_tool()[1]['changes']['mods']['name_spelling_changed']), 1)

    def test_no_unicode_normalization(self):
        self.set_lists('+caf\u00e9\n', '+cafe\u0301\n')
        self.assertEqual(len(self.run_tool()[1]['changes']['mods']['added']), 1)

    def test_duplicates_and_casefold_collisions_refused(self):
        for text in ('+A\n-A\n', '+A\n+a\n', '+Stra\u00dfe\n+STRASSE\n'):
            with self.subTest(text=text):
                self.set_lists(text, '')
                self.incomplete('duplicate_or_case_colliding_name')

    def test_strict_names_and_markers(self):
        for text in ('A', '+../A', '+A/B', '+A\\B', '+NUL.txt', '+A:stream', '+A ', '+ A', '+', ' +A', '?A'):
            with self.subTest(text=text):
                self.set_lists(text, '')
                self.assertEqual(self.run_tool()[0], 1)

    def test_unsupported_encoding_and_controls(self):
        for data, expected in ((b'\xff', 'unsupported_encoding'), (b'+A\0\n', 'invalid_modlist_text'),
                               (b'+A\x7f', 'invalid_modlist_text')):
            with self.subTest(data=data):
                self.set_lists(data, b'')
                self.incomplete(expected)

    def test_bom_newlines_comments_and_format_only_changes(self):
        for newline in ('\r\n', '\r', '\n'):
            with self.subTest(newline=newline):
                self.set_lists('\ufeff# original comment'+newline+'+A'+newline+newline+'-B', '+A\n-B\n# other comment\n')
                status, report = self.run_tool()
                self.assertEqual(status, 0)
                self.assertFalse(report['input_bytes_equal'])
                self.assertEqual(report['before']['entries'][0]['line'], 2)
                self.assertTrue(report['before']['bom'])

    def test_comments_not_exported(self):
        self.set_lists('# private comment must be omitted\n+A\n', '+A\n')
        self.assertNotIn('private comment', json.dumps(self.run_tool()[1]))

    def test_unicode_line_separator_not_split_as_new_entry(self):
        self.set_lists('+A\u2028+B\n', '+A\u2028+B\n')
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertEqual(len(report['before']['entries']), 1)

    def test_empty_saved_lists(self):
        self.set_lists('', '# empty\n')
        self.assertEqual(self.run_tool()[0], 0)

    def test_same_file_allowed(self):
        self.assertEqual(self.run_tool(after=self.before)[0], 0)

    def test_line_length_and_line_count_limits(self):
        self.set_lists('#'+'x'*tool.LINE_LIMIT, '')
        self.incomplete('line_length_limit')
        self.set_lists('\n'*tool.LINE_COUNT_LIMIT, '')
        self.incomplete('line_count_limit')

    def test_entry_limit(self):
        self.set_lists(''.join(f'+M{i}\n' for i in range(tool.ENTRY_LIMIT+1)), '')
        self.incomplete('entry_count_limit')

    def test_mod_name_length_boundary(self):
        self.set_lists('+'+'A'*255+'\n', '+'+'A'*255+'\n')
        self.assertEqual(self.run_tool()[0], 0)
        self.set_lists('+'+'A'*256+'\n', '')
        self.incomplete('unsafe_mod_name')

    def test_reverse_comparison_swaps_direction(self):
        self.set_lists('+A\n-B\n+Old\n', '-A\n+B\n+New\n')
        forward = self.run_tool()[1]['summary']['mods']
        reverse = self.run_tool(before=self.after, after=self.before)[1]['summary']['mods']
        for first, second in (('added','removed'), ('removed','added'), ('enabled','disabled'), ('disabled','enabled')):
            self.assertEqual(forward[first], reverse[second])

    def test_complete_report_is_deterministic(self):
        self.set_lists('+A\n+B\n', '-B\n+A\n+New\n')
        self.assertEqual(self.run_tool()[1], self.run_tool()[1])

    def test_output_limit_failure_has_no_partial_data(self):
        args = ['--before', str(self.before), '--after', str(self.after)]
        # The real report is larger than this cap, but the fallback fits.
        fallback_size = len(tool.encode(tool.blank()))
        import contextlib
        import io
        output = io.StringIO()
        with mock.patch.object(tool, 'REPORT_LIMIT', fallback_size+100), contextlib.redirect_stdout(output):
            status = tool.main(args)
        report = json.loads(output.getvalue())
        self.assertEqual(status, 1)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['before'])
        self.assertEqual(report['errors'][0]['code'], 'report_byte_limit')

    def test_file_byte_limit(self):
        self.set_lists(b'#'*(tool.FILE_LIMIT+1), b'')
        self.incomplete('file_byte_limit')

    def test_after_error_role_and_line(self):
        self.set_lists('+A\n', '# comment\n+A\n+a\n')
        status, report = self.run_tool()
        self.assertEqual(status, 1)
        self.assertEqual(report['errors'][0]['input'], 'after')
        self.assertEqual(report['errors'][0]['line'], 3)

    def test_new_output_and_exclusive_protection(self):
        output = self.root/'report.json'
        self.assertEqual(self.run_tool('--output', output)[0], 0)
        before = output.read_bytes()
        self.assertEqual(self.run_tool('--output', output)[0], 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(self.run_tool('--output', self.before)[0], 1)
        self.assertEqual(self.run_tool('--output', self.after)[0], 1)

    def test_missing_input_directory_and_missing_output_parent(self):
        self.assertEqual(self.run_tool(before=self.root/'missing')[0], 1)
        self.assertEqual(self.run_tool(before=self.root)[0], 1)
        self.assertEqual(self.run_tool('--output', self.root/'absent'/'report.json')[0], 1)

    def test_invalid_arguments_sanitized(self):
        status, report = self.run_tool('--unknown', 'private path')
        self.assertEqual(status, 1)
        self.assertEqual(report['errors'][0]['code'], 'invalid_arguments')

    def test_input_change_detected_before_publishing_comparison(self):
        original = tool.compare
        def mutate(*args):
            result = original(*args)
            self.before.write_bytes(b'+changed\n')
            return result
        args = tool.parser().parse_args(['--before', str(self.before), '--after', str(self.after)])
        with mock.patch.object(tool, 'compare', side_effect=mutate):
            report, target = tool.inspect(args)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['before'])
        self.assertEqual(report['errors'][0]['code'], 'input_changed')

    def test_report_and_accounting_limits(self):
        with mock.patch.object(tool, 'REPORT_LIMIT', 10), self.assertRaises(tool.Failure):
            tool.encode({'name': 'long value'})
        with mock.patch.object(tool, 'METADATA_LIMIT', 10), self.assertRaises(tool.Failure):
            tool.parse_modlist(b'+A\n', tool.Budget())

    def test_linked_input_and_parent_rejected(self):
        link = self.root/'linked.txt'
        try:
            link.symlink_to(self.before)
        except OSError:
            self.skipTest('Native symlink creation unavailable')
        self.assertEqual(self.run_tool(before=link)[0], 1)
        folder = self.root/'linked-folder'
        folder.symlink_to(self.root, target_is_directory=True)
        try:
            self.assertEqual(self.run_tool('--output', folder/'new.json')[0], 1)
        finally:
            folder.unlink()

    @unittest.skipUnless(os.name == 'nt', 'Windows junction fixture')
    def test_windows_junction_input_output_rejected(self):
        target = self.root/'real'
        target.mkdir()
        (target/'modlist.txt').write_bytes(self.before.read_bytes())
        link = self.root/'junction'
        escaped_link, escaped_target = str(link).replace("'", "''"), str(target).replace("'", "''")
        result = subprocess.run(['powershell', '-NoProfile', '-Command',
            f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            self.skipTest('Native junction creation unavailable')
        self.assertTrue(link.lstat().st_file_attributes & 0x400)
        try:
            self.assertEqual(self.run_tool(before=link/'modlist.txt')[0], 1)
            self.assertEqual(self.run_tool('--output', link/'report.json')[0], 1)
        finally:
            self.assertTrue(link.lstat().st_file_attributes & 0x400)
            link.rmdir()

    def test_path_policy(self):
        for value in ('//host/share/file', 'C:relative', 'NUL.txt', 'a:stream'):
            with self.subTest(value=value), self.assertRaises(tool.Failure):
                tool.local_path(value)

    def test_output_race_preserves_existing_file(self):
        target = self.root/'report.json'
        target.write_bytes(b'existing data')
        with self.assertRaises(tool.Failure):
            tool.write(b'new data', target)
        self.assertEqual(target.read_bytes(), b'existing data')

    def test_all_small_permutations_against_pairwise_oracle(self):
        before = list('ABCDE')
        for after in itertools.permutations(before):
            expected = set()
            ranks = {name: i for i, name in enumerate(after)}
            for i, left in enumerate(before):
                for right in before[i+1:]:
                    if ranks[left] > ranks[right]:
                        expected.update((left, right))
            found = tool.inversions(before, after)
            self.assertEqual(set(found), expected)
            for key, row in found.items():
                witness = row['crossed_key']
                self.assertLess((before.index(key)-before.index(witness))*(ranks[key]-ranks[witness]), 0)

    def test_insert_remove_randomized_order_oracle(self):
        rng = random.Random(20261023)
        for unused in range(100):
            old = rng.sample(list('ABCDEFGHIJ'), rng.randint(0,10))
            new = rng.sample(list('ABCDEFGHIJ'), rng.randint(0,10))
            shared = set(old) & set(new)
            expected = {left for left in shared for right in shared
                        if (old.index(left)-old.index(right))*(new.index(left)-new.index(right)) < 0}
            self.assertEqual(set(tool.inversions(old,new)), expected)

    def test_original_example_commands(self):
        folder = self.root/'example'
        result = subprocess.run([sys.executable, '-B', str(GENERATOR), '--destination', str(folder)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        status, report = self.run_tool(before=folder/'before/modlist.txt', after=folder/'after/modlist.txt')
        self.assertEqual(status, 2)
        self.assertEqual(report['summary']['mods'], {'added':1, 'removed':1, 'name_spelling_changed':0,
                                                    'reordered':3, 'enabled':1, 'disabled':1})
        self.assertEqual(report['summary']['separators']['relocated'], 1)
        first = (folder/'before/modlist.txt').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(GENERATOR), '--destination', str(folder)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((folder/'before/modlist.txt').read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
