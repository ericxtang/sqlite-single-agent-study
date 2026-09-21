import hashlib
from pathlib import Path
import tempfile
import unittest

from slt import Normalizer, Reference, counts, digest, matches, records, score_file


class EvaluationTests(unittest.TestCase):
    def fixture(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'case.test'
        path.write_text(text)
        return path

    def test_skip_halt_and_fixed_denominator(self):
        p = self.fixture('skipif SQLite\nquery I\nSELECT 1\n----\n1\n\nonlyif SQLite\nquery I\nSELECT 2\n----\n2\n\nhalt\n\nquery I\nSELECT 3\n----\n3\n')
        self.assertEqual(counts(p), {'queries': 1, 'statements': 0, 'skipped_queries': 1, 'skipped_statements': 0})

    def test_condition_header_allows_upstream_comments(self):
        p = self.fixture('skipif mysql # empty RHS\nquery I\nSELECT 1\n----\n1\n')
        self.assertEqual(counts(p)['queries'], 1)

    def test_reference_null_sort_hash_errors_and_state(self):
        h = digest(['1', '2'])
        p = self.fixture('statement ok\nCREATE TABLE t(x INTEGER)\n\nstatement ok\nINSERT INTO t VALUES (2),(1)\n\nquery I rowsort same\nSELECT x FROM t\n----\n1\n2\n\nquery I rowsort same\nSELECT x FROM t\n----\n2 values hashing to ' + h + '\n\nstatement error\nINSERT INTO missing VALUES (1)\n\nquery T\nSELECT NULL\n----\nNULL\n')
        result = score_file(p, Reference())
        self.assertEqual(result['queries_passed'], 3)
        self.assertEqual(result['statements_passed'], 3)
        self.assertFalse(result['tainted'])

    def test_failed_setup_preserves_unreached_queries(self):
        p = self.fixture('statement ok\nNOT VALID SQL\n\nquery I\nSELECT 1\n----\n1\n\nquery I\nSELECT 2\n----\n2\n')
        result = score_file(p, Reference())
        self.assertEqual(result['queries'], 2)
        self.assertEqual(result['queries_failed'], 2)
        self.assertTrue(result['tainted'])

    def test_incorrect_query_does_not_hide_later_query(self):
        p = self.fixture('query I\nSELECT 1\n----\n2\n\nquery I\nSELECT 2\n----\n2\n')
        result = score_file(p, Reference())
        self.assertEqual(result['queries_passed'], 1)
        self.assertEqual(result['queries_failed'], 1)
        self.assertFalse(result['tainted'])

    def test_type_normalization_matches_original_adapter(self):
        n = Normalizer()
        self.assertEqual(n.cell({'type': 'integer', 'value': '4294967295'}, 'I'), '-1')
        self.assertEqual(n.cell({'type': 'real', 'value': '1.125'}, 'R'), '1.125')
        self.assertEqual(n.cell({'type': 'text', 'value': ''}, 'T'), '(empty)')
        self.assertEqual(n.cell({'type': 'text', 'value': 'a\né\0hidden'}, 'T'), 'a@@@')
        self.assertEqual(n.cell({'type': 'null'}, 'R'), 'NULL')

    def test_hash_checks_value_count(self):
        value_hash = hashlib.md5(b'1\n').hexdigest()
        self.assertTrue(matches(['1'], (f'1 values hashing to {value_hash}',)))
        self.assertFalse(matches(['1'], (f'2 values hashing to {value_hash}',)))

    def test_reject_unknown_controls(self):
        p = self.fixture('include other.test\n')
        with self.assertRaises(ValueError):
            list(records(p))

    def test_malformed_output_is_failure_not_exclusion(self):
        class Broken(Reference):
            def request(self, request):
                if request['op'] == 'execute':
                    return {'ok': True, 'columns': [], 'rows': []}
                return super().request(request)
        p = self.fixture('query I\nSELECT 1\n----\n1\n')
        result = score_file(p, Broken())
        self.assertEqual(result['queries_failed'], 1)
        self.assertTrue(result['tainted'])


if __name__ == '__main__':
    unittest.main()
