"""One-pass, pre-frozen holdout size and independent PCM gate; no timing claim."""
import json
from pathlib import Path
from types import SimpleNamespace

from benchmark_speed_first import ROOT, load_cases, validate_sized, size_check
from benchmark_effort8 import LibFLAC, library, sha, command_for, measure


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--set', choices=['1','2'], required=True)
    p.add_argument('--attempt', default='')
    args = p.parse_args()
    suffix = '' if args.set == '1' else '2'
    evidence = ROOT / 'validation/evidence'
    report_path = evidence / f'speed-first-revision3-holdout{suffix}-gate{args.attempt}.json'
    assert not report_path.exists(), 'Preserve first holdout result'
    identity_path = evidence / 'speed-first-candidate-revision3.json'
    identity = json.loads(identity_path.read_text())
    manifest = evidence / f'speed-first-holdout{suffix}-manifest.json'
    assert sha(manifest) == identity[f'holdout{suffix}_manifest_sha256']
    for path, digest in identity['sources'].items():
        assert sha(ROOT / path) == digest
    binaries = {'baseline': ROOT / '_build/speed-first/accepted-baseline.exe',
                'candidate': ROOT / identity['cli']['path']}
    assert sha(binaries['candidate']) == identity['cli']['sha256']
    baseline = json.loads((evidence / 'speed-first-baseline.json').read_text())
    assert sha(binaries['baseline']) == 'e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743'
    opts = SimpleNamespace(flac=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe',
                           ffmpeg='ffmpeg', timeout=1800)
    ref = LibFLAC(library(None))
    work = ROOT / f'validation/cache/speed-first-revision3-holdout{suffix}-gate{args.attempt}'
    work.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', method=__doc__, cases=[],
                  candidate_identity_sha256=sha(identity_path),
                  baseline_identity_sha256=sha(evidence / 'speed-first-baseline.json'),
                  manifest_sha256=sha(manifest), script_sha256=sha(Path(__file__)))

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    try:
        for case in load_cases(manifest):
            assert sha(ROOT / case['path']) == case['pcm_sha256']
            row = dict(case, codecs={})
            report['cases'].append(row)
            for codec, binary in binaries.items():
                output = work / f'{case["name"]}-{codec}.flac'
                command = command_for(codec, binary, case, output, False, 1)
                measured = measure(command, opts.timeout)
                checked = validate_sized(output, case, ref, opts)
                row['codecs'][codec] = dict(command=command, **measured, **checked)
                save()
            b, c = row['codecs']['baseline'], row['codecs']['candidate']
            row['size_budget'] = size_check(b['encoded_bytes'], c['encoded_bytes'], 1.03)
            for value in row['codecs'].values():
                value['file_to_pcm_ratio'] = value['encoded_bytes'] / case['pcm_bytes']
                value['payload_to_pcm_ratio'] = value['payload_bytes'] / case['pcm_bytes']
            save()
            print(case['name'], row['size_budget'], flush=True)
        totals = {k: sum(c['codecs'][k]['encoded_bytes'] for c in report['cases']) for k in binaries}
        report['aggregate_size_budget'] = size_check(totals['baseline'], totals['candidate'], 1.01)
        passed = report['aggregate_size_budget']['passed'] and all(c['size_budget']['passed'] for c in report['cases'])
        report['status'] = 'pass' if passed else 'failed_budget'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()
    if report['status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
