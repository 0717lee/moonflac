"""Small balanced engineering A/B; never a final libFLAC victory measurement."""
import argparse
import json
import statistics
import subprocess
from pathlib import Path

import psutil
from benchmark_effort8 import ROOT, sha
from benchmark_faster_than_libflac import artifact_identity, source_identity


def verified_oracle(report_path, manifest_path, mode='core'):
    """Bind expected bytes to the complete independently checked input set."""
    oracle = json.loads(report_path.read_text())
    assert mode in ['core', 'cli']
    assert oracle['manifest']['sha256'] == sha(manifest_path)
    cases = json.loads(manifest_path.read_text())['cases']
    fixed_manifest = oracle['status'] == 'pass' and 'aggregate' in oracle
    if fixed_manifest:
        assert oracle['aggregate'][mode]['passed']
        rows = {row['name']: row for row in oracle['cases']}
    else:
        assert oracle['status'] == 'complete' and oracle['quality_pass']
        assert oracle['mode'] == mode and oracle['group'] == 'original-' + mode
        rows = {row['case']['name']: row for row in oracle['cases']}
    assert len(rows) == len(oracle['cases']) == len(cases)
    expected = {}
    for case in cases:
        row = rows[case['name']]
        if fixed_manifest:
            assert row['pcm_sha256'] == case['pcm_sha256']
            assert row['cli_core_byte_identity']
            assert row['outputs'][mode]['size_budget']['passed']
            checked = row['outputs'][mode]['verification']
        else:
            assert row['case']['pcm_sha256'] == case['pcm_sha256']
            for field in ['channels', 'bits', 'rate', 'block', 'samples']:
                assert row['case'][field] == case[field], field
            checked = row['warmup']['candidate']['verification']
        assert checked['libflac_pcm'] == checked['ffmpeg_pcm'] == 'exact'
        assert checked['flac_md5_crc'] == 'pass'
        expected[case['name']] = checked['encoded_sha256']
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a-identity', type=Path, required=True)
    parser.add_argument('--b-identity', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--batch', type=int, default=3)
    parser.add_argument('--oracle-report', type=Path,
                        default=ROOT / 'validation/evidence/faster-than-libflac-candidate4-core-diagnostic.json')
    parser.add_argument('--b-oracle-report', type=Path,
                        help='Separate complete independent oracle when B changes compressed bytes')
    parser.add_argument('--cases', nargs='+', help='Explicit diagnostic subset; default is every frozen original12 case')
    args = parser.parse_args()
    assert args.batch > 0 and not args.report.exists()
    assert args.label and all(c.isalnum() or c in '-_' for c in args.label)
    work = ROOT / '_build/faster-than-libflac' / args.label
    work.mkdir(exist_ok=False)
    psutil.Process().cpu_affinity([8])
    identities = {role: json.loads(p.read_text()) for role, p in [('a', args.a_identity), ('b', args.b_identity)]}
    binaries = {role: ROOT / info['core']['path'] for role, info in identities.items()}
    for role, binary in binaries.items():
        assert sha(binary) == identities[role]['core']['sha256']
    bindings = {role: dict(artifact=artifact_identity(path, binaries[role], 'core'),
                           sources=source_identity(path))
                for role, path in [('a', args.a_identity), ('b', args.b_identity)]}
    manifest = ROOT / 'validation/evidence/faster-than-libflac-inputs-original-core.json'
    cases = json.loads(manifest.read_text())['cases']
    all_names = [case['name'] for case in cases]
    if args.cases is None:
        args.cases = all_names
    assert len(set(args.cases)) == len(args.cases), 'Duplicate case selection'
    assert set(args.cases) <= set(all_names), 'Unknown case selection'
    oracle_report = args.oracle_report
    b_oracle_report = args.b_oracle_report or oracle_report
    expected = {'a': verified_oracle(oracle_report, manifest),
                'b': verified_oracle(b_oracle_report, manifest)}
    report = dict(status='running', scope=__doc__, acceptance_eligible=False, cpu=8, rounds=4, batch=args.batch,
                  identities={role: dict(path=str(p), sha256=sha(p)) for role, p in [('a', args.a_identity), ('b', args.b_identity)]},
                  bindings=bindings, script_sha256=sha(Path(__file__)),
                  manifest_sha256=sha(manifest), selected_cases=args.cases,
                  all_original_cases_selected=set(args.cases) == set(all_names),
                  verified_pcm_crc_md5_report=dict(path=str(oracle_report), sha256=sha(oracle_report)),
                  b_verified_pcm_crc_md5_report=dict(path=str(b_oracle_report), sha256=sha(b_oracle_report)), cases=[])

    def save():
        args.report.write_text(json.dumps(report, indent=2) + '\n')

    try:
        for case in cases:
            if case['name'] not in args.cases:
                continue
            assert sha(ROOT / case['path']) == case['pcm_sha256']
            row = dict(name=case['name'], observations=[])
            report['cases'].append(row)
            for repetition in range(4):
                for role in (['a', 'b'] if repetition % 2 == 0 else ['b', 'a']):
                    output = work / (case['name'] + '-' + role + '.flac')
                    command = [str(binaries[role]), str(ROOT / case['path']), str(output), str(case['channels']),
                               str(case['bits']), str(case['rate']), str(case['block']), str(args.batch), '8']
                    process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
                    line = next(line for line in process.stdout.splitlines() if line.startswith('MOON_CORE '))
                    measured = json.loads(line[len('MOON_CORE '):])
                    assert measured['batch'] == args.batch and sha(output) == expected[role][case['name']]
                    row['observations'].append(dict(role=role, round=repetition, seconds=measured['seconds']/args.batch,
                                                    raw=measured, command=command, verified_output_sha256=sha(output)))
                    save()
            medians = {role: statistics.median([v['seconds'] for v in row['observations'] if v['role'] == role]) for role in binaries}
            row.update(medians=medians, b_over_a=medians['b']/medians['a'])
            print(row['name'], row['b_over_a'], medians, flush=True)
        assert len(report['cases']) == len(args.cases)
        for role, binary in binaries.items():
            assert sha(binary) == identities[role]['core']['sha256']
        for role, path in [('a', args.a_identity), ('b', args.b_identity)]:
            assert bindings[role]['artifact'] == artifact_identity(path, binaries[role], 'core')
            assert bindings[role]['sources'] == source_identity(path)
        assert expected['a'] == verified_oracle(oracle_report, manifest)
        assert expected['b'] == verified_oracle(b_oracle_report, manifest)
        report.update(status='pass', note='Every output matches its role-specific complete independent PCM/CRC/MD5 and size oracle. This is an A/B engineering diagnostic, not a libFLAC comparison.')
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
