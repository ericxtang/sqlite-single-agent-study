import unittest
from secondary import ReferenceLab, run_suite


class Broken:
    def request(self, request):
        return {'ok': True, 'columns': [], 'rows': []}


class BrokenLab(ReferenceLab):
    def start(self, case):
        return Broken()

    def verify_file(self, case):
        raise ValueError('No file from broken fixture')


class SecondaryTests(unittest.TestCase):
    def test_reference_passes_all_cases(self):
        lab = ReferenceLab()
        try:
            result = run_suite(lab)
            self.assertEqual(result['passed'], 12, result)
        finally:
            lab.close()

    def test_empty_success_responses_fail_every_case(self):
        lab = BrokenLab()
        try:
            result = run_suite(lab)
            self.assertEqual(result['passed'], 0, result)
            self.assertEqual(result['total'], 12)
        finally:
            lab.close()
