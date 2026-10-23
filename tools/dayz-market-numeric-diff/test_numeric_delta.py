"""Synthetic tests only; no actual DayZ templates or runtime dependencies.
Copyright (c) 2026 TheOutlandsDev. SPDX-License-Identifier: MIT
"""
import copy
import hashlib
import json
import unittest
import numeric_delta as mod

class NumericDeltaTests(unittest.TestCase):
    def setUp(self):
        self.before = {'InitStockPercent':75,'IsExchange':0,'DisplayName':'Synthetic',
            'Items':[{'ClassName':'SyntheticA','MaxStockThreshold':1,'Variants':['SyntheticVariant']},
                     {'ClassName':'SyntheticB','MaxStockThreshold':1}]}
        self.raw=json.dumps(self.before).encode()
        self.sha=hashlib.sha256(self.raw).hexdigest()
    def test_one_changed_item_does_not_touch_equal_unchanged_value(self):
        after=copy.deepcopy(self.before)
        after['Items'][0]['MaxStockThreshold']=50
        result=mod.derive_numeric_changes(self.before,after)
        self.assertEqual(len(result['operations']),1)
        self.assertEqual(mod.preview_exact_baseline(self.raw,self.sha,result['operations']),after)
        self.assertNotIn('ClassName',json.dumps(result))
        self.assertNotIn('SyntheticVariant',json.dumps(result))
    def test_noop(self):
        result=mod.derive_numeric_changes(self.before,copy.deepcopy(self.before))
        self.assertEqual(result['operations'],[])
        self.assertTrue(result['numeric_replay_matches_complete_observation'])
    def test_unselected_text_is_not_copied(self):
        after=copy.deepcopy(self.before)
        after['DisplayName']='Unselected private-looking sentinel'
        result=mod.derive_numeric_changes(self.before,after)
        self.assertTrue(result['unselected_differences_present'])
        self.assertNotIn('sentinel',json.dumps(result))
    def test_reorder_is_held(self):
        after=copy.deepcopy(self.before)
        after['Items'].reverse()
        after['Items'][0]['MaxStockThreshold']=25
        result=mod.derive_numeric_changes(self.before,after)
        self.assertEqual(result['operations'],[])
        self.assertEqual(result['held_identity_or_added_removed_positions'],2)
    def test_added_item_is_not_copied(self):
        after=copy.deepcopy(self.before)
        after['Items'].append({'ClassName':'NewUnreviewedItem','MaxStockThreshold':2})
        result=mod.derive_numeric_changes(self.before,after)
        self.assertNotIn('NewUnreviewedItem',json.dumps(result))
        self.assertTrue(result['unselected_differences_present'])
    def test_wrong_hash(self):
        with self.assertRaises(ValueError):
            mod.preview_exact_baseline(self.raw,'0'*64,[])
    def test_wrong_before_value(self):
        with self.assertRaises(ValueError):
            mod.preview_exact_baseline(self.raw,self.sha,[{'op':'set_existing_numeric_field','pointer':'/InitStockPercent','before':1,'after':2}])
    def test_unsafe_or_unselected_pointers(self):
        for pointer in ('/DisplayName','/Items/0/ClassName','/../x','/Items/-1/MaxStockThreshold','/Items/00/MaxStockThreshold'):
            with self.subTest(pointer=pointer),self.assertRaises(ValueError):
                mod.preview_exact_baseline(self.raw,self.sha,[{'op':'set_existing_numeric_field','pointer':pointer,'before':1,'after':2}])
    def test_duplicate_pointer(self):
        op={'op':'set_existing_numeric_field','pointer':'/InitStockPercent','before':75,'after':2}
        with self.assertRaises(ValueError):
            mod.preview_exact_baseline(self.raw,self.sha,[op,op])
    def test_bool_is_not_numeric(self):
        after=copy.deepcopy(self.before)
        after['InitStockPercent']=True
        self.assertEqual(mod.derive_numeric_changes(self.before,after)['operations'],[])
        self.assertTrue(mod.derive_numeric_changes(self.before,after)['unselected_differences_present'])
        self.assertFalse(mod.derive_numeric_changes(self.before,after)['numeric_replay_matches_complete_observation'])
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            mod.load_market(b'{"Items":[],"InitStockPercent":NaN}')
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            mod.load_market(b'{"Items":[],"Items":[]}')
    def test_preview_preserves_input(self):
        original=self.raw
        mod.preview_exact_baseline(self.raw,self.sha,[])
        self.assertEqual(self.raw,original)
    def test_large_integer_is_finite_without_float_conversion(self):
        self.assertTrue(mod.numeric(10**400))
    def test_boolean_and_integer_in_unselected_nested_field_differ(self):
        before=copy.deepcopy(self.before)
        before['Extra']={'nested':[1]}
        after=copy.deepcopy(before)
        after['Extra']['nested'][0]=True
        result=mod.derive_numeric_changes(before,after)
        self.assertTrue(result['unselected_differences_present'])
        self.assertFalse(result['numeric_replay_matches_complete_observation'])
    def test_exponent_overflow_rejected(self):
        with self.assertRaises(ValueError):
            mod.load_market(b'{"Items":[],"InitStockPercent":1e400}')
    def test_object_nonfinite_rejected(self):
        before=copy.deepcopy(self.before)
        before['Extra']=float('inf')
        with self.assertRaises(ValueError):
            mod.derive_numeric_changes(before,self.before)
    def test_deep_parsed_and_object_trees_rejected(self):
        nested=0
        for _ in range(80): nested=[nested]
        before=copy.deepcopy(self.before)
        before['Extra']=nested
        with self.assertRaises(ValueError):
            mod.derive_numeric_changes(before,self.before)
        with self.assertRaises(ValueError):
            mod.load_market(json.dumps(before).encode())
    def test_decoder_recursion_rejected(self):
        raw=b'{"Items":[],"Extra":'+b'['*1200+b'0'+b']'*1200+b'}'
        with self.assertRaises(ValueError): mod.load_market(raw)
    def test_cycles_rejected(self):
        before=copy.deepcopy(self.before)
        before['Extra']=before
        with self.assertRaises(ValueError): mod.derive_numeric_changes(before,self.before)
    def test_node_limit(self):
        before=copy.deepcopy(self.before)
        before['Extra']=[0]*mod.MAX_NODES
        with self.assertRaises(ValueError): mod.derive_numeric_changes(before,self.before)
    def test_text_limit(self):
        before=copy.deepcopy(self.before)
        before['Extra']='x'*(mod.MAX_INPUT_BYTES+1)
        with self.assertRaises(ValueError): mod.derive_numeric_changes(before,self.before)
    def test_int_and_float_are_same_json_numeric_value(self):
        after=copy.deepcopy(self.before)
        after['InitStockPercent']=75.0
        self.assertTrue(mod.derive_numeric_changes(self.before,after)['numeric_replay_matches_complete_observation'])

if __name__=='__main__':
    unittest.main()
