"""Verify the portable release and create a distinct, local replication seal."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def release_verify():
    manifest=json.loads((ROOT/'publication-manifest.json').read_text())
    for name,sha in manifest['files'].items():
        if digest(ROOT/name)!=sha:raise RuntimeError('Public input changed: '+name)
    return digest(ROOT/'publication-manifest.json')
def local_inputs():
    names=['publication-manifest.json','records/runtime-image.json','records/astra-mcp-only-catalog.json','records/doctor.json']
    cli=Path(shutil.which('codex')).resolve()
    return {**{n:digest(ROOT/n) for n in names},'codex_executable':digest(cli)}
def verify():
    release_verify()
    seal=json.loads((ROOT/'records/replication-seal.json').read_text())
    if local_inputs()!=seal['files']:raise RuntimeError('Replication configuration changed; use a new clone/protocol')
    if (ROOT/'records/STOP').exists():raise RuntimeError('STOP exists; preserve previous outputs before a separately authorized restart')
    if subprocess.check_output(['codex','--version'],text=True).strip()!='codex-cli 0.153.0':raise RuntimeError('CLI version changed')
    image=json.loads((ROOT/'records/runtime-image.json').read_text())['id']
    subprocess.run(['docker','image','inspect',image],check=True,stdout=subprocess.DEVNULL)
    return digest(ROOT/'records/replication-seal.json')
