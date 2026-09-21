import sys
import unittest

from process import JsonProcess


class ProtocolTests(unittest.TestCase):
    def engine(self, program, **kwargs):
        result = JsonProcess([sys.executable, '-u', '-c', program], **kwargs)
        self.addCleanup(result.close)
        return result

    def test_roundtrip(self):
        p = self.engine('import sys,json\nfor line in sys.stdin:\n print(json.dumps({"ok":True,"request":json.loads(line)}),flush=True)')
        self.assertEqual(p.request({'op': 'open'})['request']['op'], 'open')

    def test_timeout(self):
        p = self.engine('import time;time.sleep(10)', timeout=0.05)
        with self.assertRaises(TimeoutError):
            p.request({'op': 'open'})

    def test_output_limit(self):
        p = self.engine('print("x"*100,flush=True)', max_bytes=20)
        with self.assertRaises(OSError):
            p.request({'op': 'open'})

    def test_invalid_json(self):
        p = self.engine('import sys\nfor line in sys.stdin: print("bad",flush=True)')
        with self.assertRaises(ValueError):
            p.request({'op': 'open'})


if __name__ == '__main__':
    unittest.main()
