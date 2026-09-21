import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'replication'))
from grade import jobs_for
from runtime_config import config_text
class ReplicationTests(unittest.TestCase):
    def test_queue_keeps_terminal_and_all_jobs(self):
        endpoints=jobs_for('endpoints');full=jobs_for('all')
        self.assertEqual(len(endpoints),8);self.assertEqual(len(full),59)
        self.assertEqual(len({(str(j['archive']),j['suite']) for j in full}),59)
        self.assertEqual(sum(j['suite']=='secondary' for j in full),4)
        self.assertEqual(sum('003' in str(j['archive']) for j in endpoints),2)
        self.assertTrue(all(j['archive'].is_file() for j in full))
    def test_config_removes_host_execution_and_agents(self):
        s=config_text('/tmp/test-config','astra-sqlite-replication-test','/tmp/test-log')
        for key in ['shell_tool','unified_exec','multi_agent','apps','plugins','browser_use','computer_use','image_generation','view_image']:
            self.assertIn(key+' = false',s)
        self.assertIn('[agents]\nenabled = false',s)
        self.assertIn('replication/container_tools.py',s)
        self.assertIn(json.dumps(sys.executable),s)
    def test_controller_lock_excludes_second_controller(self):
        from execution_lock import acquire
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'lock'
            with acquire(path):
                with self.assertRaises(RuntimeError):acquire(path)
            with acquire(path):pass
    def test_public_usage_and_cost_arithmetic(self):
        d=json.loads((ROOT/'historical/records/usage-accounting.json').read_text())
        expected={'measured-001':70.898888,'measured-002':71.595192,'measured-004':74.764858}
        for run in d['runs']:
            if run['run_id'] not in expected:continue
            t=run['deduplicated_response_usage_sum']
            self.assertEqual(t,run['last_thread_token_usage'])
            val=((t['input_tokens']-t['cached_input_tokens']-t['cache_write_input_tokens'])*10+t['cached_input_tokens']+t['cache_write_input_tokens']*12.5+t['output_tokens']*50)/1e6
            self.assertAlmostEqual(val,expected[run['run_id']],places=6)
if __name__=='__main__':unittest.main()
