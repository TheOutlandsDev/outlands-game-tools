"""Black-box XML comparison checks with original generated XML only. MIT."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.parsers import expat

SCRIPT = Path(__file__).resolve().parents[1] / "xml_diff.py"
EXAMPLE = SCRIPT.parent / "examples" / "create_example.py"


class XmlDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if tuple(expat.version_info) < (2, 7, 2):
            raise RuntimeError("Tests require an actual Expat >= 2.7.2 runtime; no silent parser-test skips.")

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xml-diff-test-")
        self.root = Path(self.temporary.name)
        self.baseline = self.root / "baseline.xml"
        self.candidate = self.root / "candidate.xml"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, baseline: str | bytes, candidate: str | bytes | None = None) -> None:
        candidate = baseline if candidate is None else candidate
        self.baseline.write_bytes(baseline.encode("utf-8") if isinstance(baseline, str) else baseline)
        self.candidate.write_bytes(candidate.encode("utf-8") if isinstance(candidate, str) else candidate)

    def run_tool(self, *extra: object, baseline: Path | None = None,
                 candidate: Path | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [str(value) for value in extra]
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--baseline",
                                 str(self.baseline if baseline is None else baseline), "--candidate",
                                 str(self.candidate if candidate is None else candidate), *arguments],
                                capture_output=True, text=True, timeout=30)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)
        payload = result.stdout
        if not payload.strip() and "--output" in arguments:
            output = Path(arguments[arguments.index("--output") + 1])
            if output.is_file():
                payload = output.read_text(encoding="utf-8")
        self.assertTrue(payload.strip(), result.stderr)
        self.assertNotIn(str(self.root), payload)
        return result, json.loads(payload)

    def assert_exit(self, baseline: str | bytes, candidate: str | bytes,
                    expected: int, *extra: object) -> dict:
        self.write(baseline, candidate)
        result, report = self.run_tool(*extra)
        self.assertEqual(result.returncode, expected, report)
        self.assertEqual(report["complete"], expected != 1)
        return report

    def test_identical_leaf_and_empty_elements(self) -> None:
        self.assert_exit('<settings><value>toy</value><empty/></settings>',
                         '<settings><value>toy</value><empty/></settings>', 0)

    def test_attribute_change(self) -> None:
        self.assert_exit('<settings slots="4"/>', '<settings slots="8"/>', 2)

    def test_added_and_removed_attributes(self) -> None:
        self.assert_exit('<settings remove="toy"/>', '<settings added="toy"/>', 2)

    def test_leaf_text_is_exact_including_whitespace(self) -> None:
        self.assert_exit('<settings> toy </settings>', '<settings>toy</settings>', 2)

    def test_element_only_indentation_comments_and_pi_are_ignored(self) -> None:
        self.assert_exit('<settings><!--toy--><value>same</value></settings>',
                         '<?toy original?><settings>\n  <value>same</value>\n</settings>', 0)

    def test_cdata_and_equivalent_character_references(self) -> None:
        self.assert_exit('<settings><![CDATA[toy < value & safe]]></settings>',
                         '<settings>toy &lt; value &amp; safe</settings>', 0)

    def test_root_tag_change_is_a_difference(self) -> None:
        self.assert_exit('<old/>', '<new/>', 2)

    def test_same_tag_root_key_change_is_an_attribute_change(self) -> None:
        report = self.assert_exit('<settings id="old"/>', '<settings id="new"/>', 2)
        self.assertEqual(report['summary']['attribute_changed'], 1)
        self.assertEqual(report['summary']['element_added'], 0)
        self.assertEqual(report['summary']['element_removed'], 0)

    def test_default_keyed_sibling_insertions_and_removals(self) -> None:
        self.assert_exit('<settings><item id="shared">same</item><item id="old"/></settings>',
                         '<settings><item id="shared">same</item><item id="new"/></settings>', 2)

    def test_default_keyed_reordering_is_reported_without_content_mismatches(self) -> None:
        report = self.assert_exit('<settings><item id="a">one</item><item id="b">two</item></settings>',
                                  '<settings><item id="b">two</item><item id="a">one</item></settings>', 2)
        self.assertEqual(report['summary']['children_reordered'], 1)
        self.assertEqual(report['summary']['text_changed'], 0)
        self.assertEqual(report['summary']['attribute_changed'], 0)

    def test_keyed_insertion_does_not_report_unrelated_child_reordering(self) -> None:
        report = self.assert_exit('<settings><item id="a"/><item id="b"/></settings>',
                                  '<settings><item id="new"/><item id="a"/><item id="b"/></settings>', 2)
        self.assertEqual(report['summary']['element_added'], 1)
        self.assertEqual(report['summary']['children_reordered'], 0)
        self.assertEqual(report['summary']['element_removed'], 0)

    def test_common_child_reordering_is_still_detected_with_an_insertion(self) -> None:
        report = self.assert_exit('<settings><item id="a"/><item id="b"/><item id="c"/></settings>',
                                  '<settings><item id="new"/><item id="c"/><item id="a"/><item id="b"/></settings>', 2)
        self.assertEqual(report['summary']['children_reordered'], 1)
        self.assertEqual(report['summary']['element_added'], 1)
        self.assertEqual(report['summary']['attribute_changed'], 0)

    def test_first_present_key_attribute_has_documented_precedence(self) -> None:
        xml = '<settings><item id="a" Name="same"/><item id="b" Name="same"/></settings>'
        self.assert_exit(xml, xml, 0)

    def test_duplicate_sibling_keys_are_rejected(self) -> None:
        xml = '<settings><item id="same"/><item id="same"/></settings>'
        self.assert_exit(xml, xml, 1)

    def test_ambiguous_keys_in_added_or_removed_subtrees_are_rejected(self) -> None:
        xml = '<settings><group><item id="same"/><item id="same"/></group></settings>'
        self.assert_exit('<settings/>', xml, 1)
        self.assert_exit(xml, '<settings/>', 1)

    def test_repeated_unkeyed_same_tag_siblings_are_rejected_by_default(self) -> None:
        xml = '<settings><item>one</item><item>two</item></settings>'
        self.assert_exit(xml, xml, 1)

    def test_explicit_ordinal_mode_compares_repeated_unkeyed_siblings(self) -> None:
        self.assert_exit('<settings><item>one</item><item>two</item></settings>',
                         '<settings><item>one</item><item>three</item></settings>', 2,
                         '--unkeyed', 'ordinal')

    def test_unique_unkeyed_tags_can_match_without_ordinal_mode(self) -> None:
        self.assert_exit('<settings><first>one</first><second>two</second></settings>',
                         '<settings><first>one</first><second>two</second></settings>', 0)

    def test_explicit_key_attribute_replaces_defaults(self) -> None:
        self.assert_exit('<settings><item code="a">one</item><item code="b">two</item></settings>',
                         '<settings><item code="b">two</item><item code="a">one</item></settings>', 2,
                         '--key-attribute', 'code')

    def test_replaced_key_policy_does_not_still_use_id(self) -> None:
        xml = '<settings><item id="a"/><item id="b"/></settings>'
        self.assert_exit(xml, xml, 1, '--key-attribute', 'code')

    def test_namespace_prefix_aliases_compare_by_expanded_names(self) -> None:
        self.assert_exit('<a:settings xmlns:a="urn:toy"><a:item a:value="same"/></a:settings>',
                         '<b:settings xmlns:b="urn:toy"><b:item b:value="same"/></b:settings>', 0)

    def test_namespace_uri_change_is_a_difference(self) -> None:
        self.assert_exit('<settings xmlns="urn:toy-one"/>',
                         '<settings xmlns="urn:toy-two"/>', 2)

    def test_explicit_namespaced_key_uses_clark_not_prefix_spelling(self) -> None:
        report = self.assert_exit('<settings xmlns:a="urn:toy"><item a:code="one">old</item><item a:code="two"/></settings>',
                                  '<settings xmlns:b="urn:toy"><item b:code="one">new</item><item b:code="two"/></settings>', 2,
                                  '--key-attribute', '{urn:toy}code')
        self.assertEqual(report['summary']['text_changed'], 1)
        self.assertEqual(report['summary']['element_added'], 0)
        self.assertEqual(report['summary']['element_removed'], 0)

    def test_nonwhitespace_mixed_content_is_rejected(self) -> None:
        for xml in ('<settings>before<value/>after</settings>',
                    '<settings><value/>tail</settings>', '<settings>head<value/></settings>'):
            with self.subTest(xml=xml):
                self.assert_exit(xml, xml, 1)

    def test_ambiguity_and_mixed_content_in_unmatched_subtrees_are_not_skipped(self) -> None:
        inputs = ('<settings><group><item/><item/></group></settings>',
                  '<settings><group>head<item/>tail</group></settings>')
        for xml in inputs:
            with self.subTest(xml=xml):
                self.assert_exit('<settings/>', xml, 1)
                self.assert_exit(xml, '<settings/>', 1)

    def test_xinclude_and_preserved_xml_space_are_rejected(self) -> None:
        inputs = ('<settings xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="unselected.xml"/></settings>',
                  '<settings xml:space="preserve"><item/></settings>',
                  '<settings xml:space="unknown"/>')
        for xml in inputs:
            with self.subTest(xml=xml):
                self.assert_exit(xml, '<settings/>', 1)

    def test_utf8_bom_is_accepted_but_other_encodings_are_rejected(self) -> None:
        xml = '<settings>caf\u00e9</settings>'
        self.assert_exit(b'\xef\xbb\xbf' + xml.encode('utf-8'), xml.encode('utf-8'), 0)
        for encoding, bom in (('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff')):
            for declaration in ('', '<?xml version="1.0" encoding="UTF-16"?>'):
                for prefix in (b'', bom):
                    with self.subTest(encoding=encoding, declared=bool(declaration), bom=bool(prefix)):
                        self.assert_exit(prefix + (declaration + xml).encode(encoding), b'<settings/>', 1)
        self.assert_exit('<?xml version="1.0" encoding="ISO-8859-1"?><settings>toy</settings>', '<settings/>', 1)

    def test_declaration_text_inside_comment_or_cdata_is_ordinary_content(self) -> None:
        self.assert_exit('<settings><!-- <!DOCTYPE toy> --><item/></settings>',
                         '<settings><item/></settings>', 0)
        self.assert_exit('<settings><![CDATA[<!DOCTYPE toy>]]></settings>',
                         '<settings>&lt;!DOCTYPE toy&gt;</settings>', 0)

    def test_malformed_and_duplicate_attribute_xml_are_rejected(self) -> None:
        for xml in ('<settings>', '<settings a="1" a="2"/>', '<settings><a></settings>',
                    '<settings/>junk', '<one/><two/>'):
            with self.subTest(xml=xml):
                self.assert_exit(xml, '<settings/>', 1)

    def test_doctype_internal_entity_and_external_entity_inputs_are_rejected(self) -> None:
        inputs = ('<!DOCTYPE settings><settings/>',
                  '<!DOCTYPE settings [<!ENTITY toy "expanded">]><settings>&toy;</settings>',
                  '<!DOCTYPE settings SYSTEM "file:///unselected-toy.xml"><settings/>')
        for xml in inputs:
            with self.subTest(xml=xml):
                self.assert_exit(xml, '<settings/>', 1)

    def test_entity_expansion_declaration_is_refused_early(self) -> None:
        xml = '<!DOCTYPE settings [<!ENTITY a "toy"><!ENTITY b "&a;&a;&a;&a;">]><settings>&b;</settings>'
        self.assert_exit(xml, '<settings/>', 1)

    def test_attribute_and_key_values_are_redacted_by_default(self) -> None:
        marker = 'unshared-toy-identity-value-27'
        self.write(f'<settings><item id="{marker}" value="private-old-text"/></settings>',
                   f'<settings><item id="{marker}" value="private-new-text"/></settings>')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report['complete'])
        for value in (marker, 'private-old-text', 'private-new-text'):
            self.assertNotIn(value, result.stdout)

    def test_leaf_values_are_redacted_by_default(self) -> None:
        self.write('<settings>private-old-toy-text</settings>',
                   '<settings>private-new-toy-text</settings>')
        result, _ = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('private-old-toy-text', result.stdout)
        self.assertNotIn('private-new-toy-text', result.stdout)

    def test_include_values_is_explicit_opt_in(self) -> None:
        self.write('<settings value="old-toy-raw">old-toy-text</settings>',
                   '<settings value="new-toy-raw">new-toy-text</settings>')
        result, _ = self.run_tool('--include-values')
        self.assertEqual(result.returncode, 2)
        for value in ('old-toy-raw', 'new-toy-raw', 'old-toy-text', 'new-toy-text'):
            self.assertIn(value, result.stdout)

    def test_changed_values_have_exact_length_and_utf8_hash_fingerprints(self) -> None:
        report = self.assert_exit('<settings value="old"/>', '<settings value="caf\u00e9"/>', 2)
        change = next(row for row in report['changes'] if row['kind'] == 'attribute_changed')
        self.assertEqual(change['before'], {'characters': 3, 'sha256': hashlib.sha256(b'old').hexdigest()})
        self.assertEqual(change['after'], {'characters': 4, 'sha256': hashlib.sha256('caf\u00e9'.encode()).hexdigest()})

    def test_added_element_has_key_fingerprint_without_subtree_text(self) -> None:
        marker = 'private-toy-added-id'
        self.write('<settings/>', f'<settings><item id="{marker}"><value>hidden-toy-subtree-text</value></item></settings>')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 2)
        row = next(change for change in report['changes'] if change['kind'] == 'element_added')
        self.assertEqual(row['subtree_elements'], 2)
        self.assertEqual(row['identity']['attribute'], 'id')
        self.assertEqual(row['identity']['value']['sha256'], hashlib.sha256(marker.encode()).hexdigest())
        self.assertNotIn(marker, result.stdout)
        self.assertNotIn('hidden-toy-subtree-text', result.stdout)

    def test_input_fingerprints_describe_original_bytes(self) -> None:
        self.write('<settings>same</settings>')
        result, report = self.run_tool()
        self.assertEqual(result.returncode, 0)
        for side, path in (('baseline', self.baseline), ('candidate', self.candidate)):
            self.assertEqual(report['inputs'][side], {'bytes': path.stat().st_size,
                                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    def test_input_bytes_and_directory_contents_remain_unchanged(self) -> None:
        self.write('<settings value="old"/>', '<settings value="new"/>')
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result, _ = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_observed_source_change_prevents_complete_comparison(self) -> None:
        self.write('<settings value="old"/>')
        bootstrap = '''
import os, runpy, sys
from pathlib import Path
original = os.fstat
target = Path(sys.argv[2])
def changed(fd):
    info = original(fd)
    os.fstat = original
    target.write_bytes(b'<settings value="changed"/>')
    return info
os.fstat = changed
sys.argv = [sys.argv[1], '--baseline', sys.argv[2], '--candidate', sys.argv[3]]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT),
                                 str(self.baseline), str(self.candidate)],
                                capture_output=True, text=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(json.loads(result.stdout)['complete'])

    def test_report_is_deterministic(self) -> None:
        self.write('<settings><item id="a" x="1">one</item></settings>',
                   '<settings><item id="a" x="2">two</item></settings>')
        first, _ = self.run_tool()
        second, _ = self.run_tool()
        self.assertEqual(first.stdout, second.stdout)

    def test_existing_output_is_not_overwritten(self) -> None:
        self.write('<settings/>')
        output = self.root / 'existing.json'
        output.write_bytes(b'keep original toy output')
        result, report = self.run_tool('--output', output)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])
        self.assertEqual(output.read_bytes(), b'keep original toy output')

    def test_output_cannot_replace_either_input(self) -> None:
        self.write('<settings/>')
        for target in (self.baseline, self.candidate):
            with self.subTest(target=target.name):
                before = target.read_bytes()
                result, report = self.run_tool('--output', target)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report['complete'])
                self.assertEqual(target.read_bytes(), before)

    def test_new_output_is_valid_json(self) -> None:
        self.write('<settings value="a"/>', '<settings value="b"/>')
        output = self.root / 'comparison.json'
        result, report = self.run_tool('--output', output)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(report['complete'])
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)

    def test_missing_input_fails_without_echoing_source_path(self) -> None:
        self.write('<settings/>')
        result, report = self.run_tool(baseline=self.root / 'missing-personal-file.xml')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_directory_as_input_is_refused(self) -> None:
        self.write('<settings/>')
        result, report = self.run_tool(baseline=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    def test_file_byte_limit(self) -> None:
        self.assert_exit('<settings>long original toy value</settings>', '<settings/>', 1,
                         '--max-bytes', 20)

    def test_depth_limit(self) -> None:
        xml = '<a><b><c/></b></a>'
        self.assert_exit(xml, xml, 1, '--max-depth', 2)

    def test_element_count_limit(self) -> None:
        xml = '<settings><a/><b/><c/></settings>'
        self.assert_exit(xml, xml, 1, '--max-elements', 3)

    def test_attribute_count_limit(self) -> None:
        xml = '<settings a="1" b="2"><item c="3"/></settings>'
        self.assert_exit(xml, xml, 1, '--max-attributes', 2)

    def test_change_count_limit_marks_comparison_incomplete(self) -> None:
        self.assert_exit('<settings a="1" b="2"/>', '<settings a="3" b="4"/>', 1,
                         '--max-changes', 1)

    def test_encoded_report_limit_is_an_incomplete_failure(self) -> None:
        length = 4 * 1024 * 1024 + 8
        self.assert_exit('<settings>' + 'a' * length + '</settings>',
                         '<settings>' + 'b' * length + '</settings>', 1,
                         '--max-bytes', 16 * 1024 * 1024, '--include-values')

    def test_invalid_or_above_hard_ceiling_limits_fail_cleanly(self) -> None:
        self.write('<settings/>')
        for option, value in (('--max-bytes', '0'), ('--max-depth', '-1'),
                              ('--max-depth', '129'), ('--max-elements', '100001'),
                              ('--max-attributes', '200001'), ('--max-changes', '100001'),
                              ('--max-bytes', str(16 * 1024 * 1024 + 1)),
                              ('--max-elements', 'not-an-integer'), ('--max-depth', '9' * 500)):
            with self.subTest(option=option, value=value[:30]):
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--baseline',
                                         str(self.baseline), '--candidate', str(self.candidate), option, value],
                                        capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)

    def test_symlink_input_is_refused(self) -> None:
        self.write('<settings/>')
        link = self.root / 'linked.xml'
        try:
            link.symlink_to(self.baseline)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'File symlinks unavailable: {type(error).__name__}')
        result, report = self.run_tool(baseline=link)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['complete'])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction/reparse-point behavior')
    def test_windows_junction_ancestor_is_refused(self) -> None:
        self.write('<settings/>')
        target = self.root / 'junction-target'
        target.mkdir()
        (target / 'baseline.xml').write_bytes(self.baseline.read_bytes())
        link = self.root / 'junction'
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        created = subprocess.run(['powershell', '-NoProfile', '-Command',
                                  f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
                                 capture_output=True, text=True, timeout=20)
        if created.returncode:
            self.skipTest('Creating a Windows junction is unavailable')
        try:
            result, report = self.run_tool(baseline=link / 'baseline.xml')
            self.assertEqual(result.returncode, 1)
            self.assertFalse(report['complete'])
            self.assertEqual((target / 'baseline.xml').read_bytes(), self.baseline.read_bytes())
        finally:
            info = link.lstat()
            self.assertTrue(getattr(info, 'st_file_attributes', 0) & 0x400)
            link.rmdir()  # Remove only this generated junction; never recurse into target.

    def test_unsupported_expat_version_is_a_controlled_failure(self) -> None:
        self.write('<settings/>')
        bootstrap = ('import runpy,sys; from xml.parsers import expat; '
                     'expat.version_info=(2,6,3); expat.EXPAT_VERSION="expat_2.6.3"; '
                     'sys.argv=[sys.argv[1],*sys.argv[2:]]; runpy.run_path(sys.argv[0],run_name="__main__")')
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(SCRIPT), '--baseline',
                                 str(self.baseline), '--candidate', str(self.candidate)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('Traceback', result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report['complete'])

    def test_generated_example_and_exclusive_destination(self) -> None:
        destination = self.root / 'example'
        result = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        compared, report = self.run_tool(baseline=destination / 'baseline.xml',
                                        candidate=destination / 'candidate.xml')
        self.assertEqual(compared.returncode, 2)
        self.assertTrue(report['complete'])
        self.assertEqual(report['summary'], {
            'baseline_elements': 4, 'candidate_elements': 4, 'matched_elements': 3,
            'changes': 4, 'element_added': 1, 'element_removed': 1,
            'attribute_added': 0, 'attribute_removed': 0, 'attribute_changed': 1,
            'text_changed': 1, 'children_reordered': 0,
        })
        attribute = next(row for row in report['changes'] if row['kind'] == 'attribute_changed')
        self.assertEqual(attribute['attribute'], 'slots')
        self.assertEqual(attribute['before'], {'characters': 1, 'sha256': hashlib.sha256(b'4').hexdigest()})
        self.assertEqual(attribute['after'], {'characters': 1, 'sha256': hashlib.sha256(b'8').hexdigest()})
        text = next(row for row in report['changes'] if row['kind'] == 'text_changed')
        self.assertEqual(text['before'], {'characters': 8, 'sha256': hashlib.sha256(b'original').hexdigest()})
        self.assertEqual(text['after'], {'characters': 7, 'sha256': hashlib.sha256(b'changed').hexdigest()})
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        again = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', str(destination)],
                               capture_output=True, text=True, timeout=20)
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(before, {path.name: path.read_bytes() for path in destination.iterdir()})

    def test_example_generator_rejects_unsafe_destinations(self) -> None:
        for destination in ('F:relative-xml-demo', '//unselected-server/share',
                            str(self.root / 'CON .xml'), str(self.root / 'CONIN$')):
            with self.subTest(destination=destination):
                result = subprocess.run([sys.executable, '-B', str(EXAMPLE), '--destination', destination],
                                        capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
