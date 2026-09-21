#!/usr/bin/env python3
"""Create a frozen semantic-reference corpus, without bundled databases or test pages."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = set('''wal spellfix1 dbstat transactional datatype3 fts5 rbu sharedcache opcode fts3 json1 partialindex backup limits capi3ref conflict sqlanalyze quirks expridx inmemorydb withoutrowid appfunc queryplanner atomiccommit capi3 series lang fullsql rowidtable nulls rtree windowfunctions rowvalue isolation lockingv3 tempfiles vfs queryplanner-ng foreignkeys bindptr optoverview vtab dbpage stricttables invalidutf percentile formatchng glossary walformat gencol affcase1 pragma bytecodevtab eqp arch schematab vdbe rescode cksumvfs printf lang_transaction base64 malloc fileformat psow howtocorrupt carray autoinc vtablist uintcseq datatypes floatingpoint threadsafe deterministic uri nulinstr mmap fileformat2 aff_short syntaxdiagrams syntax session sessionintro loadext recovery zipfile unionvtab swarmvtab geopoly base85 c_interface cin tro'''.split())


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.skip += 1
        if not self.skip and tag in ('p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'pre'):
            self.parts.append('\n')
        if not self.skip and tag in ('td', 'th'):
            self.parts.append('\t')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head') and self.skip:
            self.skip -= 1
        if not self.skip and tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'pre'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def main():
    destination = ROOT / 'inputs' / 'manual'
    if destination.exists():
        raise SystemExit('Manual already exists; version a new corpus instead of overwriting it.')
    destination.mkdir(parents=True)
    files = []
    excluded = []
    with zipfile.ZipFile(ROOT / 'downloads/sqlite-doc-3530400.zip') as z:
        for name in sorted(z.namelist()):
            rel = PurePosixPath(name).relative_to('sqlite-doc-3530400')
            if rel.suffix != '.html':
                continue
            eligible = rel.parts[0] in ('c3ref', 'syntax') or (len(rel.parts) == 1 and (rel.stem.startswith('lang') or rel.stem in REFERENCES))
            if not eligible:
                excluded.append(str(rel))
                continue
            parser = Text()
            raw = z.read(name)
            parser.feed(raw.decode('utf-8'))
            text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', ''.join(parser.parts)).strip() + '\n'
            if re.search(r'sqllogictest|sql logic test', text, re.I):
                raise SystemExit('Selected documentation mentions the held-out evaluation: ' + str(rel))
            out = rel.with_suffix('.txt')
            p = destination / out
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            files.append({'path': str(out), 'source_path': str(rel), 'source_sha256': hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size})
    index = '# SQLite 3.53.4 semantic reference\n\nFiles are text extracts of the official documentation. Paths mirror the original HTML references.\n\n' + '\n'.join('- ' + f['path'] for f in files) + '\n'
    (destination / 'INDEX.md').write_text(index)
    manifest = {'version': '3.53.4', 'source': 'https://www.sqlite.org/2026/sqlite-doc-3530400.zip', 'selection': 'SQL language and syntax, C API, and selected semantic/storage/extension reference pages. No test-suite, release-history, source-download, or marketing pages. No binary/DB/JS files.', 'equivalent_to_cursor_manual': False, 'files': files, 'index_sha256': hashlib.sha256(index.encode()).hexdigest(), 'excluded_html': excluded}
    (ROOT / 'records/documentation-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'documents': len(files), 'bytes': sum(f['bytes'] for f in files), 'excluded_html': len(excluded)}, indent=2))


if __name__ == '__main__':
    main()
