"""Explicit Docker integration test; run separately from fast evaluator unit tests."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='sqlite-evaluator-check-') as temporary:
        base = Path(temporary)
        archive = base / 'fixture.tar.gz'
        files = {
            'Cargo.toml': '[package]\nname="sqlite-agent"\nversion="0.1.0"\nedition="2021"\n',
            'src/main.rs': '''use std::io::{self, BufRead, Write};
fn main() {
    for line in io::stdin().lock().lines() {
        let line = match line { Ok(v) => v, Err(_) => break };
        if line.contains("open") || line.contains("close") {
            println!("{{\\\"ok\\\":true,\\\"columns\\\":[],\\\"rows\\\":[]}}");
        } else {
            println!("{{\\\"ok\\\":false,\\\"error\\\":\\\"deliberately incorrect fixture\\\"}}");
        }
        io::stdout().flush().unwrap();
    }
}
''',
        }
        with tarfile.open(archive, 'w:gz') as tar:
            for name, source in files.items():
                data = source.encode()
                item = tarfile.TarInfo(name)
                item.size = len(data)
                item.mode = 0o644
                tar.addfile(item, io.BytesIO(data))
        archive.with_suffix('.gz.json').write_text(json.dumps({'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'elapsed_seconds': 0}))
        report = base / 'report'
        subprocess.run([sys.executable, str(ROOT / 'evaluator/evaluate_snapshot.py'), '--archive', str(archive), '--output', str(report), '--limit-files', '2'], check=True)
        summary = json.loads((report / 'summary.json').read_text())
        assert summary['build_ok'], (report / 'build.log').read_text()
        assert summary['evaluation_complete']
        assert summary['files_scored'] == 2
        assert summary['queries'] > 0
        assert summary['queries_passed'] == 0
        assert summary['queries_failed'] == summary['queries']
        (ROOT / 'records/evaluator-integration.json').write_text(json.dumps({'passed': True, 'test': 'Deliberately incorrect Rust engine built and evaluated in isolated containers; all eligible queries failed and remained in denominator.', 'summary': summary}, indent=2) + '\n')
        secondary_report = base / 'secondary-report'
        subprocess.run([sys.executable, str(ROOT / 'evaluator/evaluate_snapshot.py'), '--archive', str(archive), '--output', str(secondary_report), '--suite', 'secondary'], check=True)
        secondary = json.loads((secondary_report / 'summary.json').read_text())
        assert secondary['build_ok'] and secondary['evaluation_complete']
        assert secondary['secondary']['passed'] == 0 and secondary['secondary']['total'] == 12
        # Verify the database transfer/reference-read route with a known-valid file.
        from secondary import ReferenceLab, run_suite
        from secondary_docker import DockerLab
        reference = ReferenceLab()
        try:
            correct = run_suite(reference)
        finally:
            reference.close()
        assert correct['passed'] == correct['total']
        image = json.loads((ROOT / 'records/runtime-image.json').read_text())['id']
        import uuid
        lab = DockerLab(image, 'unused', 'astra-sqlite-interop-probe-' + uuid.uuid4().hex[:8], ['--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,nosuid,size=512m'])
        try:
            lab.seed('roundtrip')
            lab.verify_file('roundtrip')
        finally:
            lab.close()
        (ROOT / 'records/secondary-validation.json').write_text(json.dumps({'passed': True, 'reference': correct, 'broken_fixture': secondary, 'isolated_file_transfer_roundtrip': True}, indent=2) + '\n')


if __name__ == '__main__':
    main()
