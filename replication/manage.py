#!/usr/bin/env python3
"""Prepare a replication without making model/API calls."""
import argparse,copy,hashlib,json,os,shutil,sqlite3,subprocess,sys,tarfile,tempfile,urllib.request
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from integrity import ROOT,digest,release_verify,local_inputs
IMAGE='sqlite-single-agent-replication:1'
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
def setup():
    release_verify()
    target=ROOT/'records/runtime-image.json'
    if target.exists():raise SystemExit('Runtime already recorded. Use a new clone for another runtime.')
    subprocess.run(['docker','build','--platform','linux/arm64','-t',IMAGE,str(ROOT/'runtime')],check=True)
    d=json.loads(subprocess.check_output(['docker','image','inspect',IMAGE],text=True))[0]
    save(target,{'id':d['Id'],'architecture':d['Architecture'],'os':d['Os'],'tag':IMAGE,'original_image_reused':False})
    print('Image built. You can now use python3 manual/lab.py console 001')
def fetch():
    release_verify()
    m=json.loads((ROOT/'records/corpus-manifest.json').read_text())
    dest=ROOT/'private/corpus/checkout/test'
    if dest.exists():
        verify_corpus(m,dest);return
    # Fossil tarball endpoints require web login on this host; use the official
    # anonymous Fossil synchronization protocol in a separate fetch-only image.
    print('Cloning the pinned official Fossil corpus; no generated code runs here.',flush=True)
    subprocess.run(['docker','build','-f',str(ROOT/'runtime/Dockerfile.corpus'),'-t','sqlite-study-corpus-fetch:1',str(ROOT/'runtime')],check=True)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        subprocess.run(['docker','run','--rm','-e','USER=replicator','--user',str(os.getuid())+':'+str(os.getgid()),
                        '--mount','type=bind,source='+str(Path(temp).resolve())+',target=/export',
                        'sqlite-study-corpus-fetch:1','sh','-c',
                        'fossil clone https://www.sqlite.org/sqllogictest/ /export/source.fossil && '
                        'mkdir /export/checkout && cd /export/checkout && '
                        'fossil open /export/source.fossil "$1"', 'fetch',m['revision']],check=True)
        source=Path(temp)/'checkout/test'
        verify_corpus(m,source)
        extracted=Path(temp)/'verified-test';extracted.mkdir()
        for entry in m['files']:
            rel=PurePosixPath(entry['path'])
            if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe corpus path')
            target=extracted/str(rel);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/str(rel),target)
        extracted.rename(dest)
    verify_corpus(m,dest)
def verify_corpus(m=None,dest=None):
    m=m or json.loads((ROOT/'records/corpus-manifest.json').read_text());dest=dest or ROOT/'private/corpus/checkout/test'
    for e in m['files']:
        if digest(dest/e['path'])!=e['sha256']:raise RuntimeError('Corpus mismatch: '+e['path'])
    print('Verified all '+str(len(m['files']))+' corpus files.')
def catalog(path):
    if list((ROOT/'runs').glob('replicate-*')):raise SystemExit('Do not change catalog after a run; use a new clone')
    d=json.loads(path.expanduser().read_text())
    models=d['models'] if isinstance(d,dict) else d
    model=next((copy.deepcopy(x) for x in models if x.get('slug')=='gpt-6-astra'),None)
    if model is None:raise SystemExit('Your local catalog has no gpt-6-astra. Do not substitute another model silently.')
    if model.get('context_window')!=272000:raise SystemExit('Catalog context differs from 272k; requires a new protocol')
    model['apply_patch_tool_type']=None
    save(ROOT/'records/astra-mcp-only-catalog.json',{'models':[model]})
    print('Local catalog prepared. Platform-supplied instructions stay private in ignored records/.')
def seal():
    release_verify();verify_corpus()
    p=ROOT/'records/replication-seal.json'
    if p.exists():raise SystemExit('Seal exists; never overwrite an experiment seal')
    if list((ROOT/'runs').glob('replicate-*')):raise SystemExit('Cannot seal after inference')
    d=json.loads((ROOT/'records/doctor.json').read_text())
    if not d.get('passed') or d['configuration']!=doctor_identity():raise SystemExit('Run doctor on current configuration first')
    save(p,{'created_at':datetime.now(timezone.utc).isoformat(),'original_study_seal':False,'files':local_inputs(),'reference_sqlite_version':sqlite3.sqlite_version})
    print('Sealed local replication; no inference started.')
def doctor_identity():
    return {n:digest(ROOT/n) for n in ['publication-manifest.json','records/runtime-image.json','records/astra-mcp-only-catalog.json']}
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for cmd in ['verify','setup','fetch-corpus','verify-corpus','doctor','seal']:sub.add_parser(cmd)
    sub.add_parser('catalog').add_argument('--from-file',type=Path,required=True)
    a=p.parse_args()
    if a.command=='verify':print('Public release verified: '+release_verify())
    elif a.command=='setup':setup()
    elif a.command=='fetch-corpus':fetch()
    elif a.command=='verify-corpus':verify_corpus()
    elif a.command=='catalog':catalog(a.from_file)
    elif a.command=='doctor':
        from doctor import main as doctor
        doctor()
    elif a.command=='seal':seal()
if __name__=='__main__':main()
