"""Fresh primary CLI/core acceptance after the exact partition-search repair.

Run only after all validation/profile/stress jobs have ended. Historical
secondary measurements remain labelled with their original revision.
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
    e = ROOT / 'validation/evidence'
    identity_path = e / 'speed-first-candidate-revision7.json'
    identity = json.loads(identity_path.read_text(encoding='utf-8'))
    assert identity['cli']['sha256'] == '71be364ccf233d29d5a3327ddd78ba7ad076bdb4c6fcc34b11a00d0a482041a9'
    for p, digest in identity['sources'].items():
        assert sha(ROOT/p) == digest
    for role in ['cli', 'core']:
        assert sha(ROOT/identity[role]['path']) == identity[role]['sha256']
    path = e / 'speed-first-revision7-benchmark-commands.json'
    assert not path.exists()
    logs = ROOT / '_build/speed-first/revision7-benchmarks'
    logs.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', identity_sha256=sha(identity_path),
                  script_sha256=sha(Path(__file__)), commands=[])
    try:
        for mode in ['cli', 'core']:
            baseline = ROOT / ('_build/speed-first/accepted-baseline.exe' if mode == 'cli' else
                '_build/speed-first/core-baseline/native/release/build/validation/benchmark8/benchmark8.exe')
            command = [sys.executable, '-X', 'utf8', str(ROOT/'scripts/benchmark_speed_first.py'), 'run',
                '--manifest', str(ROOT/f'validation/cache/effort8-benchmark/{mode}-inputs.json'),
                '--baseline', str(baseline), '--candidate', str(ROOT/identity[mode]['path']),
                '--candidate-identity', str(identity_path),
                '--report', str(e/f'speed-first-revision7-{mode}-benchmark.json')]
            if mode == 'core':
                command.append('--core')
            row = dict(name=mode, command=command, status='running', log=str((logs/(mode+'.log')).relative_to(ROOT)))
            print('START', mode, flush=True)
            report['commands'].append(row)
            path.write_text(json.dumps(report, indent=2)+'\n')
            with (logs/(mode+'.log')).open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=14400)
            row.update(status='pass' if result.returncode == 0 else 'failed', exit_code=result.returncode)
            result.check_returncode()
            print('DONE', mode, flush=True)
        for p, digest in identity['sources'].items():
            assert sha(ROOT/p) == digest
        for role in ['cli', 'core']:
            assert sha(ROOT/identity[role]['path']) == identity[role]['sha256']
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
