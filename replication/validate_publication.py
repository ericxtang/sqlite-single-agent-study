"""Check release checksums, retained archive identity and public evidence completeness."""
import hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def main():
    from integrity import release_verify,digest
    release_verify()
    provenance=json.loads((ROOT/'historical/bundled-originals.json').read_text())
    for rel,entry in provenance.items():
        assert digest(ROOT/rel)==entry['sha256'],rel
    archives=list((ROOT/'results').glob('*/checkpoints/*.tar.gz'))
    assert len(archives)==55,len(archives)
    for archive in archives:
        meta=json.loads(archive.with_suffix('.gz.json').read_text())
        assert digest(archive)==meta['sha256'],archive
        with tarfile.open(archive) as tar:
            for member in tar:
                p=PurePosixPath(member.name)
                assert not p.is_absolute() and '..' not in p.parts,member.name
                assert member.isfile() or member.isdir() or member.issym(),member.name
                if member.issym():
                    p=PurePosixPath(member.linkname);assert not p.is_absolute() and '..' not in p.parts
                assert not any(x in ['auth.json','.env','sessions'] for x in PurePosixPath(member.name).parts),member.name
    data=json.loads((ROOT/'reports/data/comparison-data.json').read_text())
    assert len(data['jobs'])==59
    for job in data['jobs']:
        archive=ROOT/job['archive'].replace('runs/','results/',1)
        summary=ROOT/job['output'].replace('runs/','results/',1)/'summary.json'
        assert digest(archive)==job['checkpoint_sha256']
        assert digest(summary)==job['summary_sha256']
        result=json.loads(summary.read_text());assert result['evaluation_complete']
    assert len(list((ROOT/'results').glob('*/evaluation/*/summary.json')))==66
    for p in [ROOT/'README.md',ROOT/'reports/comparison.md',*list((ROOT/'docs').glob('*.md'))]:
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text()):
            if link.startswith(('http:','https:','#','mailto:')):continue
            assert (p.parent/link.split('#')[0]).exists(),(p,link)
    print('PASS: public checksums, 55 archives, 59 completed logical jobs / 66 attempts, and public links.')
if __name__=='__main__':main()
