"""The v1 probes, changing only byte-equivalent blob comparison."""
import importlib.util
import re
from pathlib import Path

spec = importlib.util.spec_from_file_location('secondary_v1_cases', Path(__file__).resolve().parents[1] / 'evaluator/secondary.py')
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def normalize_blobs(rows):
    if not isinstance(rows, list):
        raise ValueError('Rows must be an array')
    answer = []
    for row in rows:
        if not isinstance(row, list):
            raise ValueError('Row must be an array')
        cells = []
        for cell in row:
            if not isinstance(cell, dict):
                raise ValueError('Typed cell must be an object')
            cell = dict(cell)
            if cell.get('type') == 'blob':
                value = cell.get('value')
                if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2})*', value):
                    raise ValueError('Blob must contain even-length hexadecimal text')
                cell['value'] = bytes.fromhex(value).hex()
            cells.append(cell)
        answer.append(cells)
    return answer


def execute(engine, sql, expected=None, ok=True):
    answer = frozen.call(engine, 'execute', sql=sql)
    if answer['ok'] != ok:
        raise ValueError('Unexpected SQL success/error')
    if expected is not None:
        wanted = [[frozen.typed(value) for value in row] for row in expected]
        if normalize_blobs(answer.get('rows')) != wanted or len(answer.get('columns', [])) != len(expected[0]):
            raise ValueError('Typed result mismatch')

frozen.execute = execute
run_suite = frozen.run_suite
ReferenceLab = frozen.ReferenceLab
CASE_NAMES = frozen.CASE_NAMES
SELECT, ROWS = frozen.SELECT, frozen.ROWS
