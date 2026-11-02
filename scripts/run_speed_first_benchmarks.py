"""Sequential final benchmarks. Start only after all build/test/profile jobs stop."""
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
    identity_path = evidence / 'speed-first-candidate-revision3.json'
    identity = json.loads(identity_path.read_text())
    for path, digest in identity['sources'].items():
        assert sha(ROOT / path) == digest
    for role in ['cli', 'core']:
        assert sha(ROOT / identity[role]['path']) == identity[role]['sha256']
    reports = evidence / 'speed-first-benchmark-commands.json'
    assert not reports.exists(), 'Preserve all timing attempts'
    logs = ROOT / '_build/speed-first/final-benchmarks'
    logs.mkdir(parents=True, exist_ok=False)
    script = ROOT / 'scripts/benchmark_speed_first.py'
    baseline_cli = ROOT / '_build/speed-first/accepted-baseline.exe'
    baseline_core = ROOT / '_build/speed-first/core-baseline/native/release/build/validation/benchmark8/benchmark8.exe'
    common = [sys.executable, '-X', 'utf8', str(script)]
    jobs = []
    for name, manifest, core in [
        ('cli', 'validation/cache/effort8-benchmark/cli-inputs.json', False),
        ('core', 'validation/cache/effort8-benchmark/core-inputs.json', True),
        ('holdout', 'validation/evidence/speed-first-holdout-manifest.json', False),
        ('block32768', 'validation/evidence/speed-first-block32768-manifest.json', False),
    ]:
        command = common + ['run', '--manifest', str(ROOT / manifest),
            '--baseline', str(baseline_core if core else baseline_cli),
            '--candidate', str(ROOT / identity['core' if core else 'cli']['path']),
            '--candidate-identity', str(identity_path),
            '--report', str(evidence / f'speed-first-{name}-benchmark.json')]
        if core:
            command += ['--core']
        jobs.append((name, command))
    jobs.append(('reference', common + ['reference-only',
        '--manifest', str(ROOT / 'validation/cache/effort8-benchmark/cli-inputs.json'),
        '--candidate-report', str(evidence / 'speed-first-cli-benchmark.json'),
        '--report', str(evidence / 'speed-first-reference-benchmark.json')]))
    ledger = dict(status='running', script_sha256=sha(Path(__file__)),
                  identity_sha256=sha(identity_path), commands=[])
    try:
        for name, command in jobs:
            log_path = logs / (name + '.log')
            row = dict(name=name, command=command, log=str(log_path), status='running')
            ledger['commands'].append(row)
            reports.write_text(json.dumps(ledger, indent=2) + '\n')
            print('START', name, flush=True)
            with log_path.open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=14400)
            row.update(exit_code=result.returncode, status='pass' if result.returncode == 0 else 'failed')
            result.check_returncode()
            print('DONE', name, flush=True)
        for path, digest in identity['sources'].items():
            assert sha(ROOT / path) == digest
        for role in ['cli', 'core']:
            assert sha(ROOT / identity[role]['path']) == identity[role]['sha256']
        ledger['status'] = 'pass'
    except BaseException as error:
        ledger.update(status='failed', error=repr(error))
        raise
    finally:
        reports.write_text(json.dumps(ledger, indent=2) + '\n')


if __name__ == '__main__':
    main()
