"""Controller-side sqllogictest parser and scorer. Never expose to implementer."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time


@dataclass
class Record:
    kind: str
    line: int
    sql: str = ''
    types: str = ''
    sort: str = 'nosort'
    label: str = ''
    expected: tuple = ()
    statement_ok: bool = True
    eligible: bool = True


def blocks(path):
    current, start = [], 0
    with Path(path).open(encoding='utf-8') as f:
        for number, line in enumerate(f, 1):
            line = line.rstrip('\r\n')
            if line.startswith('#'):
                continue
            if not line.strip():
                if current:
                    yield start, current
                    current = []
                continue
            if not current:
                start = number
            current.append(line)
        if current:
            yield start, current


def records(path):
    for line, block in blocks(path):
        eligible = True
        while block and block[0].split()[0] in ('skipif', 'onlyif'):
            condition, engine = block.pop(0).split('#', 1)[0].split()
            matches = engine.lower() == 'sqlite'
            eligible &= not matches if condition == 'skipif' else matches
        if not block:
            raise ValueError(f'{path}:{line}: condition without record')
        header = block[0].split('#', 1)[0].split()
        if header[0] == 'halt':
            break
        if header[0] == 'hash-threshold':
            if len(header) != 2 or not header[1].isdigit():
                raise ValueError(f'{path}:{line}: invalid hash-threshold')
            continue
        if header[0] == 'statement':
            if len(header) != 2 or header[1] not in ('ok', 'error'):
                raise ValueError(f'{path}:{line}: unsupported statement header')
            yield Record('statement', line, '\n'.join(block[1:]), statement_ok=header[1] == 'ok', eligible=eligible)
        elif header[0] == 'query':
            if not 2 <= len(header) <= 4 or re.fullmatch('[ITR]+', header[1]) is None:
                raise ValueError(f'{path}:{line}: unsupported query header')
            sort = header[2] if len(header) > 2 else 'nosort'
            if sort not in ('nosort', 'rowsort', 'valuesort'):
                raise ValueError(f'{path}:{line}: unsupported sort mode')
            split = block.index('----') if '----' in block else len(block)
            yield Record('query', line, '\n'.join(block[1:split]), header[1], sort, header[3] if len(header) > 3 else '', tuple(block[split + 1:]), eligible=eligible)
        else:
            raise ValueError(f'{path}:{line}: unsupported control {header[0]}')


def counts(path):
    result = {'queries': 0, 'statements': 0, 'skipped_queries': 0, 'skipped_statements': 0}
    for record in records(path):
        key = 'queries' if record.kind == 'query' else 'statements'
        result[('' if record.eligible else 'skipped_') + key] += 1
    return result


def typed(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, int):
        return {'type': 'integer', 'value': str(value)}
    if isinstance(value, float):
        return {'type': 'real', 'value': repr(value)}
    if isinstance(value, bytes):
        return {'type': 'blob', 'value': value.hex()}
    return {'type': 'text', 'value': value}


class Reference:
    def __init__(self):
        self.connection = None

    def request(self, request):
        if request['op'] == 'open':
            if self.connection:
                self.connection.close()
            self.connection = sqlite3.connect(request['path'], isolation_level=None)
            return {'ok': True, 'columns': [], 'rows': []}
        if request['op'] == 'close':
            if self.connection:
                self.connection.close()
                self.connection = None
            return {'ok': True, 'columns': [], 'rows': []}
        try:
            cursor = self.connection.execute(request['sql'])
            return {'ok': True, 'columns': [c[0] for c in cursor.description or []], 'rows': [[typed(v) for v in row] for row in cursor.fetchall()]}
        except sqlite3.Error as exc:
            return {'ok': False, 'error': str(exc)}


class Normalizer:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:')

    def cell(self, cell, expected_type):
        if not isinstance(cell, dict):
            raise ValueError('Cell must be an object')
        kind = cell.get('type')
        if kind == 'null':
            return 'NULL'
        raw = cell.get('value')
        if not isinstance(raw, str):
            raise ValueError('Non-null cell value must be a string')
        if kind == 'integer':
            if not re.fullmatch(r'-?\d+', raw):
                raise ValueError('Invalid integer')
            value = int(raw)
            if not -(2**63) <= value < 2**63:
                raise ValueError('Integer outside SQLite range')
        elif kind == 'real':
            value = float(raw)
        elif kind == 'text':
            value = raw
        elif kind == 'blob':
            value = bytes.fromhex(raw)
        else:
            raise ValueError('Unknown cell type')
        if expected_type == 'I':
            integer = value if kind == 'integer' else self.connection.execute('SELECT CAST(? AS INTEGER)', (value,)).fetchone()[0]
            return str((integer + 2**31) % 2**32 - 2**31)
        if expected_type == 'R':
            return self.connection.execute("SELECT printf('%.3f', ?)", (value,)).fetchone()[0]
        if kind == 'blob':
            encoded = value
        elif kind == 'text':
            encoded = value.encode('utf-8')
        elif kind == 'integer':
            encoded = str(value).encode()
        else:
            encoded = self.connection.execute('SELECT CAST(? AS TEXT)', (value,)).fetchone()[0].encode('utf-8')
        encoded = encoded.split(b'\0', 1)[0]
        return ''.join(chr(v) if 32 <= v <= 126 else '@' for v in encoded) if encoded else '(empty)'

    def rows(self, response, record):
        columns = response.get('columns')
        rows = response.get('rows')
        if not isinstance(columns, list) or len(columns) != len(record.types) or not isinstance(rows, list):
            raise ValueError('Invalid row/column shape')
        rendered = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(record.types):
                raise ValueError('Invalid row width')
            rendered.append([self.cell(cell, kind) for cell, kind in zip(row, record.types)])
        if record.sort == 'rowsort':
            rendered.sort()
        values = [cell for row in rendered for cell in row]
        if record.sort == 'valuesort':
            values.sort()
        return values


def digest(values):
    h = hashlib.md5()
    for value in values:
        h.update(value.encode('utf-8') + b'\n')
    return h.hexdigest()


def matches(values, expected):
    if len(expected) == 1:
        hashed = re.fullmatch(r'(\d+) values hashing to ([0-9a-fA-F]{32})', expected[0])
        if hashed:
            return len(values) == int(hashed[1]) and digest(values) == hashed[2].lower()
    return tuple(values) == expected


def score_file(path, engine, normalizer=None, file_timeout=300):
    total = counts(path)
    result = dict(total, queries_passed=0, statements_passed=0, failures=[], tainted=False)
    normalizer = normalizer or Normalizer()
    labels = {}
    start = time.monotonic()
    try:
        if engine.request({'op': 'open', 'path': ':memory:'}).get('ok') is not True:
            raise ValueError('Open failed')
        for record in records(path):
            if not record.eligible:
                continue
            if time.monotonic() - start > file_timeout:
                raise TimeoutError('File deadline reached')
            response = engine.request({'op': 'execute', 'sql': record.sql})
            if not isinstance(response, dict) or type(response.get('ok')) is not bool:
                raise ValueError('Malformed response')
            if record.kind == 'statement':
                if response['ok'] != record.statement_ok:
                    raise ValueError(f'Unexpected statement result at line {record.line}')
                result['statements_passed'] += 1
                continue
            if not response['ok']:
                if len(result['failures']) < 20:
                    result['failures'].append({'line': record.line, 'reason': 'query error'})
                continue
            values = normalizer.rows(response, record)
            correct = matches(values, record.expected)
            if record.label:
                signature = (len(values), digest(values))
                if record.label in labels:
                    correct &= labels[record.label] == signature
                else:
                    labels[record.label] = signature
            if correct:
                result['queries_passed'] += 1
            elif len(result['failures']) < 20:
                result['failures'].append({'line': record.line, 'reason': 'result mismatch'})
    except (ValueError, TypeError, KeyError, OverflowError, OSError, TimeoutError) as exc:
        result['tainted'] = True
        result['abort_reason'] = str(exc)
    result['queries_failed'] = total['queries'] - result['queries_passed']
    result['statements_failed'] = total['statements'] - result['statements_passed']
    result['elapsed_seconds'] = time.monotonic() - start
    return result


def corpus_manifest(root):
    files = []
    for path in sorted(Path(root).rglob('*.test')):
        files.append({'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size, **counts(path)})
    return {'files': files, 'totals': {k: sum(f[k] for f in files) for k in ('queries', 'statements', 'skipped_queries', 'skipped_statements')}}
