"""Balanced original12 CLI engineering comparison, never final acceptance."""
import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

import psutil
from benchmark_effort8 import ROOT, sha
from benchmark_faster_than_libflac import artifact_identity, source_identity
from compare_faster_core_variants import verified_oracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a-identity', type=Path, required=True)
    parser.add_argument('--b-identity', type=Path, required=True)
    parser.add_argument('--oracle-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    assert not args.report.exists()
    assert args.label and all(c.isascii() and (c.isalnum() or c in '-_') for c in args.label)
    work = ROOT / '_build/faster-than-libflac' / args.label
    work.mkdir(exist_ok=False)
    psutil.Process().cpu_affinity([8])
    identity_paths = {'a': args.a_identity, 'b': args.b_identity}
    identities = {role: json.loads(path.read_text()) for role, path in identity_paths.items()}
    binaries = {role: ROOT / value['cli']['path'] for role, value in identities.items()}
    bindings = {role: dict(artifact=artifact_identity(path, binaries[role], 'cli'),
                          sources=source_identity(path)) for role, path in identity_paths.items()}
    manifest = ROOT / 'validation/evidence/faster-than-libflac-inputs-original-cli.json'
    cases = json.loads(manifest.read_text())['cases']
    expected = verified_oracle(args.oracle_report, manifest, mode='cli')
    report = dict(status='running', scope=__doc__, acceptance_eligible=False,
                  timing_domain='whole CLI process wall time, including process startup, input/output and complete encoding',
                  cpu=8, rounds=4, warmups_per_case_per_role=1, bindings=bindings,
                  manifest_sha256=sha(manifest),
                  independent_oracle=dict(path=str(args.oracle_report), sha256=sha(args.oracle_report)),
                  scripts={str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
                      ROOT/'scripts/benchmark_faster_than_libflac.py',
                      ROOT/'scripts/compare_faster_core_variants.py']}, cases=[])

    def save():
        args.report.write_text(json.dumps(report, indent=2)+'\n')

    def run(case, role):
        output = work / (case['name']+'-'+role+'.flac')
        command = [str(binaries[role]), 'encode', str(ROOT/case['path']), str(output),
                   '--raw', '--channels', str(case['channels']), '--bits', str(case['bits']),
                   '--sample-rate', str(case['rate']), '--block-size', str(case['block']), '--effort', '8']
        report['last_command'] = command
        started = time.perf_counter()
        process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        elapsed = time.perf_counter()-started
        if process.returncode:
            report['failed_process'] = dict(command=command, returncode=process.returncode,
                                             stdout=process.stdout, stderr=process.stderr)
            raise RuntimeError('CLI exited with '+str(process.returncode))
        digest = sha(output)
        assert digest == expected[case['name']], 'Output differs from independent oracle'
        return dict(role=role, seconds=elapsed, command=command, output_sha256=digest,
                    stdout=process.stdout, stderr=process.stderr)

    try:
        for case in cases:
            assert sha(ROOT/case['path']) == case['pcm_sha256']
            assert case.get('effort', 8) == 8 and not case.get('variable', False)
            row = dict(name=case['name'], warmups=[], observations=[])
            report['cases'].append(row)
            for role in ['a', 'b']:
                row['warmups'].append(run(case, role))
            for repetition in range(4):
                for role in (['a', 'b'] if repetition % 2 == 0 else ['b', 'a']):
                    row['observations'].append(dict(round=repetition, **run(case, role)))
                    save()
            row['medians'] = {role: statistics.median(x['seconds'] for x in row['observations']
                                                    if x['role'] == role) for role in binaries}
            row['b_over_a'] = row['medians']['b']/row['medians']['a']
            assert sha(ROOT/case['path']) == case['pcm_sha256']
            print(row['name'], row['b_over_a'], row['medians'], flush=True)
        for role, path in identity_paths.items():
            assert bindings[role]['artifact'] == artifact_identity(path, binaries[role], 'cli')
            assert bindings[role]['sources'] == source_identity(path)
        assert expected == verified_oracle(args.oracle_report, manifest, mode='cli')
        report.update(status='pass', aggregate_median_ratio=
                      sum(x['medians']['b'] for x in report['cases']) /
                      sum(x['medians']['a'] for x in report['cases']),
                      note='Four balanced AB/BA rounds; all original12 retained. Every output matches the bound independent PCM/CRC/MD5 oracle. No libFLAC victory claim.')
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
