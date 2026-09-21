"""Only SQL and explicitly tested database files enter generated-code containers."""
import json
from pathlib import Path
import subprocess
import sys

from process import JsonProcess
from secondary import ReferenceLab


class DockerLab(ReferenceLab):
    def __init__(self, image, code_volume, prefix, common):
        super().__init__()
        self.image, self.code_volume, self.prefix, self.common = image, code_volume, prefix, common
        self.keepers = {}
        self.processes = []
        self.serial = 0

    def path(self, case):
        return '/work/test.db'

    def keeper(self, case):
        if case not in self.keepers:
            name = self.prefix + '-data-' + str(len(self.keepers))
            self.keepers[case] = name
            subprocess.run(['docker', 'run', '-d', '--name', name, *self.common, '--mount', f'type=volume,source={name},target=/work', self.image], check=True, stdout=subprocess.DEVNULL)
        return self.keepers[case]

    def start(self, case):
        keeper = self.keeper(case)
        self.serial += 1
        name = self.prefix + '-case-' + str(self.serial)
        engine = JsonProcess(['docker', 'run', '--rm', '-i', '--name', name, *self.common, '--mount', f'type=volume,source={keeper},target=/work', '--mount', f'type=volume,source={self.code_volume},target=/code,readonly', self.image, 'timeout', '--kill-after=2s', '180', '/code/target/release/sqlite-agent'])
        self.processes.append((engine, name))
        return engine

    def stop(self, engine):
        engine.close()
        for candidate, name in self.processes:
            if candidate is engine:
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def seed(self, case):
        keeper = self.keeper(case)
        reference = ReferenceLab()
        try:
            reference.seed(case)
            data = Path(reference.path(case)).read_bytes()
            subprocess.run(['docker', 'exec', '-i', keeper, 'python3', '-c', "import sys; open('/work/test.db','wb').write(sys.stdin.buffer.read())"], input=data, check=True, capture_output=True)
        finally:
            reference.close()

    def verify_file(self, case):
        # Reference SQLite parses the file in a separate, bounded trusted process.
        destination = self.root / (case + '.db')
        result = subprocess.run(['docker', 'cp', self.keeper(case) + ':/work/test.db', str(destination)], capture_output=True)
        if result.returncode:
            raise ValueError('Generated database file missing')
        program = '''import sqlite3,sys
from pathlib import Path
from secondary import SELECT,ROWS
c=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True)
assert c.execute(SELECT).fetchall()==ROWS
assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
'''
        try:
            result = subprocess.run([sys.executable, '-c', program, str(destination)], cwd=Path(__file__).resolve().parent, capture_output=True, timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError('Reference file read deadline') from exc
        if result.returncode:
            raise ValueError('Reference SQLite file readback or quick_check failed')

    def close(self):
        for engine, name in self.processes:
            self.stop(engine)
        for name in self.keepers.values():
            subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['docker', 'volume', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.temporary.cleanup()
