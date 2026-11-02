"""Complete the declared 32768 transport retry and unchanged reference comparison.

The original failed benchmark and the three passed sets are preserved.
Requires the independent 32768 native-FFmpeg limitation reproduction first.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'validation/evidence'
    proof = json.loads((evidence / 'speed-first-ffmpeg-32768.json').read_text())
    assert proof['status'] == 'pass'
    identity_path = evidence / 'speed-first-candidate-revision3.json'
    identity = json.loads(identity_path.read_text())
    for path, digest in identity['sources'].items():
        assert sha(ROOT/path) == digest
    cli = ROOT / identity['cli']['path']
    assert sha(cli) == identity['cli']['sha256']
    destination = evidence / 'speed-first-benchmark-completion-commands.json'
    assert not destination.exists()
    logs = ROOT / '_build/speed-first/final-benchmarks-completion'
    logs.mkdir(parents=True, exist_ok=False)
    common = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/benchmark_speed_first.py')]
    jobs = [('block32768', common + ['run', '--large-frame-transport',
        '--manifest', str(evidence / 'speed-first-block32768-manifest.json'),
        '--baseline', str(ROOT / '_build/speed-first/accepted-baseline.exe'),
        '--candidate', str(cli), '--candidate-identity', str(identity_path),
        '--report', str(evidence / 'speed-first-block32768-packetized-benchmark.json')]),
        ('reference', common + ['reference-only',
         '--manifest', str(ROOT / 'validation/cache/effort8-benchmark/cli-inputs.json'),
         '--candidate-report', str(evidence / 'speed-first-cli-benchmark.json'),
         '--report', str(evidence / 'speed-first-reference-benchmark.json')])]
    report = dict(status='running', script_sha256=sha(Path(__file__)), commands=[],
                  preserved_initial_ledger_sha256=sha(evidence / 'speed-first-benchmark-commands.json'),
                  reference_transport_proof_sha256=sha(evidence / 'speed-first-ffmpeg-32768.json'))
    try:
        for name, command in jobs:
            row = dict(name=name, command=command, status='running')
            report['commands'].append(row)
            destination.write_text(json.dumps(report, indent=2)+'\n')
            with (logs / (name+'.log')).open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=7200)
            row.update(status='pass' if result.returncode == 0 else 'failed', exit_code=result.returncode)
            result.check_returncode()
        assert sha(cli) == identity['cli']['sha256']
        for path, digest in identity['sources'].items():
            assert sha(ROOT/path) == digest
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        destination.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
