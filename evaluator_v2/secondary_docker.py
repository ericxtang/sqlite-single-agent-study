"""Same twelve probes and isolation, with v2 container evidence."""
import subprocess
import sys
import uuid
from pathlib import Path
from container import Container, InfrastructureError, checked, command, volume_create, volume_remove
from process import JsonProcess
from secondary import ReferenceLab

class DockerLab(ReferenceLab):
    def __init__(self, image, code_volume, evidence):
        super().__init__()
        self.image, self.code_volume, self.evidence = image, code_volume, evidence
        self.keepers = {}
        self.volumes = []
        self.processes = []

    def path(self, case):
        return '/work/test.db'

    def keeper(self, case):
        if case not in self.keepers:
            volume = volume_create('sqlite-eval-v2-data-' + uuid.uuid4().hex)
            self.volumes.append(volume)
            keeper = Container(self.image, ['--mount', f'type=volume,source={volume},target=/work'], ['sleep', 'infinity'], self.evidence / (case + '-keeper'))
            self.keepers[case] = (keeper, volume)
            keeper.start_keeper()
        return self.keepers[case]

    def start(self, case):
        _, volume = self.keeper(case)
        options = ['--mount', f'type=volume,source={volume},target=/work', '--mount', f'type=volume,source={self.code_volume},target=/code,readonly']
        engine = JsonProcess(self.image, options, ['timeout', '--kill-after=2s', '180', '/code/target/release/sqlite-agent'], self.evidence / (case + '-process-' + str(len(self.processes))))
        self.processes.append(engine)
        return engine

    def stop(self, engine):
        engine.close()

    def seed(self, case):
        keeper, _ = self.keeper(case)
        reference = ReferenceLab()
        try:
            reference.seed(case)
            checked(['exec', '-i', keeper.id, 'python3', '-c', "import sys; open('/work/test.db','wb').write(sys.stdin.buffer.read())"], input=Path(reference.path(case)).read_bytes())
        finally:
            reference.close()

    def verify_file(self, case):
        keeper, _ = self.keeper(case)
        state = keeper.inspect('reference_read')
        if not state['Running']:
            raise InfrastructureError('File keeper unexpectedly stopped')
        destination = self.root / (case + '.db')
        result = command(['exec', keeper.id, 'test', '-f', '/work/test.db'])
        if result.returncode == 1:
            raise ValueError('Generated database file missing')
        if result.returncode != 0:
            raise InfrastructureError('Could not inspect generated file')
        checked(['cp', keeper.id + ':/work/test.db', str(destination)])
        program = '''import sqlite3,sys
from pathlib import Path
from secondary import SELECT,ROWS
c=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True)
assert c.execute(SELECT).fetchall()==ROWS
assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
'''
        try:
            result = subprocess.run([sys.executable, '-c', program, str(destination)], cwd=Path(__file__).resolve().parents[1] / 'evaluator', capture_output=True, timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError('Reference file read deadline') from exc
        (self.evidence / (case + '-reference.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise ValueError('Reference SQLite file readback or quick_check failed')

    def close(self):
        errors = []
        for engine in self.processes:
            try: engine.close()
            except Exception as exc: errors.append(str(exc))
        for keeper, _ in self.keepers.values():
            try: keeper.close()
            except Exception as exc: errors.append(str(exc))
        for volume in self.volumes:
            try: volume_remove(volume)
            except Exception as exc: errors.append(str(exc))
        self.temporary.cleanup()
        if errors:
            raise InfrastructureError('; '.join(errors))
