"""Original offline rules/graph fixtures; no installed content, upstream parser or network. MIT."""
import contextlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'dependency_checker.py'
GENERATOR = SCRIPT.parent / 'examples/create_example.py'
spec = importlib.util.spec_from_file_location('dependency_checker', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def rule(label, kind, source, target):
    return {'id': label, 'type': kind, 'mod': source, 'target': target}


def documents(names, rules):
    return {'schema_version': 1, 'load_order': names}, {'schema_version': 1, 'rules': rules}


def evaluate(names, rules):
    left, right = documents(names, rules)
    budget = tool.Budget()
    return tool.evaluate(tool.inventory_document(json.dumps(left).encode(), budget),
                         tool.rules_document(json.dumps(right).encode(), budget), budget)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dependency-check-')
        self.root = Path(self.temp.name)
        self.inventory, self.rules = self.root/'inventory.json', self.root/'rules.json'
        self.write(['Core', 'Addon'], [rule('addon-core', 'requires', 'Addon', 'Core')])

    def tearDown(self):
        self.temp.cleanup()

    def write(self, names, rules):
        for path, document in zip((self.inventory, self.rules), documents(names, rules)):
            path.write_text(json.dumps(document, ensure_ascii=True), encoding='utf-8')

    def run_tool(self, *options, inventory=None, rules=None):
        args = [sys.executable, '-B', str(SCRIPT), '--inventory', str(inventory or self.inventory), '--rules', str(rules or self.rules)]
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
        self.assertIsNone(report['inventory'])
        self.assertIsNone(report['rule_catalog'])
        self.assertEqual(report['evaluations'], [])
        self.assertEqual(report['findings'], [])
        self.assertEqual(report['catalog_cycles'], [])
        self.assertIn(expected, [row['code'] for row in report['errors']])

    def test_satisfied_and_input_preservation(self):
        original = self.inventory.read_bytes(), self.rules.read_bytes()
        status, report = self.run_tool()
        self.assertEqual(status, 0)
        self.assertTrue(report['complete'])
        self.assertFalse(report['review_required'])
        self.assertEqual(report['evaluations'][0]['result'], 'satisfied')
        self.assertEqual((self.inventory.read_bytes(), self.rules.read_bytes()), original)

    def test_missing_requirement_and_inactive_source(self):
        self.write(['Addon'], [rule('r1', 'requires', 'Addon', 'Core'), rule('r2','requires','Absent','Other')])
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual([r['result'] for r in report['evaluations']], ['missing_requirement','not_applicable'])
        self.assertEqual(report['findings'], [{'rule_id':'r1','code':'missing_requirement'}])

    def test_requirement_does_not_imply_order(self):
        self.write(['Addon','Core'], [rule('r1','requires','Addon','Core')])
        self.assertEqual(self.run_tool()[0], 0)

    def test_conflicts_are_symmetric_presence_checks(self):
        for names in (['A','B'], ['B','A']):
            with self.subTest(names=names):
                rows, findings, cycles = evaluate(names,[rule('r1','conflicts','A','B')])
                self.assertEqual(rows[0]['result'], 'active_conflict')
        self.write(['B'], [rule('r1','conflicts','A','B')])
        self.assertEqual(self.run_tool()[1]['evaluations'][0]['result'], 'not_applicable')

    def test_load_before_positions_and_missing_endpoint(self):
        self.write(['B','A'], [rule('order','load_before','A','B'), rule('unused','load_before','C','B')])
        status, report = self.run_tool()
        self.assertEqual(status, 2)
        self.assertEqual(report['evaluations'][0]['mod_position'],2)
        self.assertEqual(report['evaluations'][0]['target_position'],1)
        self.assertEqual([row['result'] for row in report['evaluations']],['load_order_violation','not_applicable'])
        self.write(['A','B'], [rule('order','load_before','A','B')])
        self.assertEqual(self.run_tool()[0],0)

    def test_transitive_requirements_are_separate_authored_rules(self):
        rows, findings, cycles = evaluate(['A'],[rule('ab','requires','A','B'),rule('bc','requires','B','C')])
        self.assertEqual([row['result'] for row in rows], ['missing_requirement','not_applicable'])
        self.assertEqual(len(findings),1)

    def test_requirement_cycle_is_advisory_not_missing(self):
        self.write(['A','B'], [rule('ab','requires','A','B'),rule('ba','requires','B','A')])
        status, report = self.run_tool()
        self.assertEqual(status,2)
        self.assertEqual(report['findings'],[])
        cycle=report['catalog_cycles'][0]
        self.assertEqual(cycle['type'],'requires')
        self.assertEqual(cycle['members'],['A','B'])
        self.assertEqual(cycle['active_members'],['A','B'])

    def test_inactive_order_cycle_still_reviews_catalog(self):
        self.write([], [rule('ab','load_before','A','B'),rule('ba','load_before','B','A')])
        status, report = self.run_tool()
        self.assertEqual(status,2)
        self.assertEqual(report['findings'],[])
        self.assertEqual(report['catalog_cycles'][0]['active_members'],[])

    def test_cycle_types_do_not_mix_into_false_cycle(self):
        self.write(['A','B'], [rule('ab','requires','A','B'),rule('ba','load_before','B','A')])
        self.assertEqual(self.run_tool()[1]['catalog_cycles'],[])

    def test_self_relations(self):
        self.write(['A'],[rule('self','requires','A','A')])
        status, report = self.run_tool()
        self.assertEqual(status,2)
        self.assertEqual(report['evaluations'][0]['result'],'satisfied')
        self.assertEqual(report['catalog_cycles'][0]['witness'],{'mods':['A','A'],'rule_ids':['self']})
        self.write(['A'],[rule('self','load_before','A','A')])
        self.assertEqual(self.run_tool()[1]['findings'][0]['code'],'load_order_violation')
        self.write(['A'],[rule('self','conflicts','A','A')])
        self.assertEqual(self.run_tool()[1]['findings'][0]['code'],'active_conflict')

    def test_one_component_not_exponential_cycle_listing(self):
        rows=[rule(f'r{i}','requires',a,b) for i,(a,b) in enumerate(itertools.permutations('ABCD',2))]
        unused, findings, cycles=evaluate(list('ABCD'),rows)
        self.assertEqual(len(cycles),1)
        self.assertEqual(len(cycles[0]['rule_ids']),12)
        self.assertEqual(set(cycles[0]['members']),set('ABCD'))

    def test_disjoint_components_and_bridge(self):
        rules=[rule('ab','requires','A','B'),rule('ba','requires','B','A'),
               rule('bc','requires','B','C'),rule('cd','requires','C','D'),rule('dc','requires','D','C')]
        unused, findings, cycles=evaluate(['A','C'],rules)
        self.assertEqual([row['members'] for row in cycles],[['A','B'],['C','D']])
        self.assertNotIn('bc',[label for row in cycles for label in row['rule_ids']])

    def test_casefold_and_display_inventory_spelling(self):
        self.write(['CORE','Stra\u00dfe'],[rule('one','requires','STRASSE','core'),rule('two','requires','Core','strasse')])
        status,report=self.run_tool()
        self.assertEqual(status,2)
        self.assertEqual(report['findings'],[])
        self.assertEqual(report['catalog_cycles'][0]['members'],['CORE','Stra\u00dfe'])

    def test_unicode_normalization_not_applied(self):
        self.write(['caf\u00e9'],[rule('one','requires','caf\u00e9','cafe\u0301')])
        self.assertEqual(self.run_tool()[1]['findings'][0]['code'],'missing_requirement')

    def test_duplicate_inventory_names_rejected(self):
        for names in (['A','A'],['A','a'],['Stra\u00dfe','STRASSE']):
            self.write(names,[])
            self.incomplete('duplicate_or_case_colliding_mod')

    def test_duplicate_rule_ids_rejected(self):
        self.write([], [rule('Rule','requires','A','B'),rule('rule','requires','C','D')])
        self.incomplete('duplicate_rule_id')

    def test_duplicate_relations_and_reversed_conflicts_rejected(self):
        for rows in ([rule('r1','requires','A','B'),rule('r2','requires','a','b')],
                     [rule('r1','conflicts','A','B'),rule('r2','conflicts','B','A')]):
            self.write([],rows)
            self.incomplete('duplicate_rule_relation')

    def test_invalid_rule_fields_types_and_id(self):
        variants=[{'id':'x','type':'requires','mod':'A'},
                  {**rule('x','requires','A','B'),'download_url':'private'},
                  rule('bad id','requires','A','B'),rule('x','unknown','A','B'),
                  rule('x',[], 'A','B'),rule('x','requires',True,'B'),None,[]]
        for row in variants:
            with self.subTest(row=row):
                self.write([], [row])
                status,report=self.run_tool()
                self.assertEqual(status,1)
                self.assertEqual(report['errors'][0]['rule'],1)

    def test_unsafe_or_nonstring_names(self):
        for name in ('../A','A/B','A\\B','NUL.txt','A:stream',' A','A ','.','',True,{},'A\x00','x'*256):
            with self.subTest(name=name):
                self.write([name],[])
                self.incomplete('invalid_mod_name')

    def test_name_boundary(self):
        self.write(['A'*255],[])
        self.assertEqual(self.run_tool()[0],0)

    def test_empty_documents_are_valid_with_explicit_coverage(self):
        self.write([],[])
        status, report=self.run_tool()
        self.assertEqual(status,0)
        self.assertEqual(report['summary']['rules'],0)
        self.assertFalse(report['policy']['compatibility_certified'])

    def test_schema_versions_and_unknown_fields(self):
        for document in ({'schema_version':True,'load_order':[]}, {'schema_version':2,'load_order':[]},
                         {'schema_version':1,'load_order':[],'other':1}, [],
                         {'schema_version':1,'load_order':{}}):
            self.inventory.write_text(json.dumps(document),encoding='utf-8')
            self.assertEqual(self.run_tool()[0],1)

    def test_duplicate_json_keys_at_both_levels(self):
        self.inventory.write_bytes(b'{"schema_version":1,"schema_version":1,"load_order":[]}')
        self.incomplete('duplicate_json_key')
        self.write([],[])
        self.rules.write_bytes(b'{"schema_version":1,"rules":[{"id":"x","id":"y","type":"requires","mod":"A","target":"B"}]}')
        self.incomplete('duplicate_json_key')

    def test_nonfinite_and_malformed_json(self):
        for data in (b'{',b'{}{}',b'{"schema_version":NaN,"load_order":[]}',b'{"schema_version":Infinity,"load_order":[]}',b'// comment\n{}'):
            self.inventory.write_bytes(data)
            self.assertEqual(self.run_tool()[0],1)

    def test_encoding_and_initial_bom(self):
        self.inventory.write_bytes(b'\xef\xbb\xbf'+self.inventory.read_bytes())
        self.assertEqual(self.run_tool()[0],0)
        self.inventory.write_bytes(b'\xff')
        self.incomplete('unsupported_encoding')

    def test_depth_preflight_ignores_escaped_strings(self):
        self.assertEqual(tool.json_document(b'{"x":"[[[\\\"{{{"}')['x'],'[[["{{{')
        self.inventory.write_bytes(b'['*9+b']'*9)
        self.incomplete('json_depth_limit')

    def test_mod_rule_and_file_limits(self):
        self.write([f'M{i}' for i in range(tool.MOD_LIMIT+1)],[])
        self.incomplete('mod_count_limit')
        self.write([], [rule(f'r{i}','requires',f'A{i}','B') for i in range(tool.RULE_LIMIT+1)])
        self.incomplete('rule_count_limit')
        self.inventory.write_bytes(b' '*(tool.FILE_LIMIT+1))
        self.incomplete('file_byte_limit')

    def test_accounting_node_and_report_limits(self):
        with mock.patch.object(tool,'METADATA_LIMIT',10),self.assertRaises(tool.Failure):
            tool.inventory_document(b'{"schema_version":1,"load_order":["A"]}',tool.Budget())
        with mock.patch.object(tool,'NODE_LIMIT',1),self.assertRaises(tool.Failure):
            evaluate([], [rule('r','requires','A','B')])
        with mock.patch.object(tool,'REPORT_LIMIT',10),self.assertRaises(tool.Failure):
            tool.encode({'x':'long content'})

    def test_output_limit_fallback_has_no_partial_inventory(self):
        cap=len(tool.encode(tool.blank()))+100
        stdout=io.StringIO()
        with mock.patch.object(tool,'REPORT_LIMIT',cap),contextlib.redirect_stdout(stdout):
            status=tool.main(['--inventory',str(self.inventory),'--rules',str(self.rules)])
        report=json.loads(stdout.getvalue())
        self.assertEqual(status,1)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['inventory'])
        self.assertEqual(report['errors'][0]['code'],'report_byte_limit')

    def test_exclusive_output_and_input_overlap(self):
        output=self.root/'report.json'
        self.assertEqual(self.run_tool('--output',output)[0],0)
        original=output.read_bytes()
        self.assertEqual(self.run_tool('--output',output)[0],1)
        self.assertEqual(output.read_bytes(),original)
        for path in (self.inventory,self.rules):
            self.assertEqual(self.run_tool('--output',path)[0],1)

    def test_bad_args_missing_input_parent_and_nonregular(self):
        self.assertEqual(self.run_tool('--unknown','private')[0],1)
        self.assertEqual(self.run_tool(inventory=self.root/'absent')[0],1)
        self.assertEqual(self.run_tool(inventory=self.root)[0],1)
        self.assertEqual(self.run_tool('--output',self.root/'absent'/'report.json')[0],1)

    def test_source_mutation_drops_all_results(self):
        original=tool.evaluate
        def mutate(*args):
            result=original(*args)
            self.inventory.write_bytes(b'changed')
            return result
        args=tool.parser().parse_args(['--inventory',str(self.inventory),'--rules',str(self.rules)])
        with mock.patch.object(tool,'evaluate',side_effect=mutate):
            report,target=tool.inspect(args)
        self.assertFalse(report['complete'])
        self.assertIsNone(report['inventory'])
        self.assertEqual(report['errors'][0]['code'],'input_changed')

    def test_same_json_file_for_roles_refused_by_schema(self):
        self.assertEqual(self.run_tool(rules=self.inventory)[0],1)

    def test_deterministic_report(self):
        self.write(['B','A'], [rule('ab','requires','A','B'),rule('ba','requires','B','A')])
        self.assertEqual(self.run_tool()[1],self.run_tool()[1])

    def test_no_expression_evaluation_or_commands(self):
        self.write(["__import__('os')"],[])
        status, report=self.run_tool()
        self.assertEqual(status,0)
        self.assertEqual(report['inventory']['load_order'],["__import__('os')"])

    def test_linked_input_output_parent_rejected(self):
        link=self.root/'linked.json'
        try:
            link.symlink_to(self.inventory)
        except OSError:
            self.skipTest('Native symlink creation unavailable')
        self.assertEqual(self.run_tool(inventory=link)[0],1)
        folder=self.root/'linked-folder'
        folder.symlink_to(self.root,target_is_directory=True)
        try:
            self.assertEqual(self.run_tool('--output',folder/'report.json')[0],1)
        finally:
            folder.unlink()

    @unittest.skipUnless(os.name=='nt','Windows junction fixture')
    def test_windows_junction_input_output_rejected(self):
        target=self.root/'real';target.mkdir()
        (target/'inventory.json').write_bytes(self.inventory.read_bytes())
        link=self.root/'junction'
        escaped_link,escaped_target=str(link).replace("'","''"),str(target).replace("'","''")
        result=subprocess.run(['powershell','-NoProfile','-Command',
            f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' -ErrorAction Stop | Out-Null"],
            capture_output=True,text=True,timeout=20)
        if result.returncode:
            self.skipTest('Native junction creation unavailable')
        self.assertTrue(link.lstat().st_file_attributes&0x400)
        try:
            self.assertEqual(self.run_tool(inventory=link/'inventory.json')[0],1)
            self.assertEqual(self.run_tool('--output',link/'report.json')[0],1)
        finally:
            self.assertTrue(link.lstat().st_file_attributes&0x400)
            link.rmdir()

    def test_path_policy_and_output_race(self):
        for value in ('//host/share/file','C:relative','NUL.json','a:stream'):
            with self.subTest(value=value),self.assertRaises(tool.Failure):
                tool.local_path(value)
        output=self.root/'report.json';output.write_bytes(b'owned elsewhere')
        with self.assertRaises(tool.Failure):tool.write(b'new',output)
        self.assertEqual(output.read_bytes(),b'owned elsewhere')

    def test_long_chain_and_cycle_use_no_python_recursion(self):
        names=[f'M{i}' for i in range(1500)]
        rules=[rule(f'r{i}','requires',names[i],names[i+1]) for i in range(len(names)-1)]
        self.assertEqual(evaluate(names,rules)[2],[])
        rules.append(rule('close','requires',names[-1],names[0]))
        self.assertEqual(len(evaluate(names,rules)[2][0]['members']),1500)

    def test_all_three_node_graphs_against_reachability_oracle(self):
        names=list('ABC');edges=list(itertools.product(names,repeat=2))
        for mask in range(1<<len(edges)):
            selected=[edge for bit,edge in enumerate(edges) if mask&(1<<bit)]
            rules=[rule(f'r{i}','requires',a,b) for i,(a,b) in enumerate(selected)]
            reach={name:set() for name in names}
            for a,b in selected:reach[a].add(b)
            for via in names:
                for a in names:
                    if via in reach[a]:reach[a].update(reach[via])
            expected={frozenset(b for b in names if b in reach[a] and a in reach[b]) for a in names if a in reach[a]}
            cycles=evaluate(names,rules)[2]
            self.assertEqual({frozenset(row['members']) for row in cycles},expected)
            by_id={row['id']:row for row in rules}
            for cycle in cycles:
                walk,ids=cycle['witness']['mods'],cycle['witness']['rule_ids']
                self.assertEqual(walk[0],walk[-1]);self.assertEqual(len(walk),len(ids)+1)
                for a,b,label in zip(walk,walk[1:],ids):
                    self.assertEqual((by_id[label]['mod'],by_id[label]['target']),(a,b))

    def test_seeded_direct_evaluation_oracle(self):
        rng=random.Random(20261023)
        for unused in range(100):
            active=rng.sample(list('ABCDE'),rng.randrange(6))
            kind=rng.choice(tool.TYPES);a,b=rng.sample(list('ABCDE'),2)
            row=evaluate(active,[rule('r',kind,a,b)])[0][0]
            if kind=='requires':expected='not_applicable' if a not in active else ('satisfied' if b in active else 'missing_requirement')
            elif kind=='conflicts':expected='active_conflict' if a in active and b in active else 'not_applicable'
            else:expected='not_applicable' if a not in active or b not in active else ('satisfied' if active.index(a)<active.index(b) else 'load_order_violation')
            self.assertEqual(row['result'],expected)

    def test_original_example_commands(self):
        folder=self.root/'example'
        result=subprocess.run([sys.executable,'-B',str(GENERATOR),'--destination',str(folder)],capture_output=True)
        self.assertEqual(result.returncode,0)
        for name,expected in (('clean',0),('review',2)):
            status,report=self.run_tool(inventory=folder/f'inventory-{name}.json',rules=folder/f'rules-{name}.json')
            self.assertEqual(status,expected)
            if name=='review':
                self.assertEqual([row['code'] for row in report['findings']],['missing_requirement','active_conflict','load_order_violation'])
                self.assertEqual(report['summary']['catalog_cycles'],{'requires':1,'load_before':1})
        original=(folder/'rules-clean.json').read_bytes()
        result=subprocess.run([sys.executable,'-B',str(GENERATOR),'--destination',str(folder)],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((folder/'rules-clean.json').read_bytes(),original)


if __name__=='__main__':
    unittest.main()
