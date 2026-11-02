"""Replay the immutable 17+14 quality sets against the original e681 anchor."""
import argparse
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from benchmark_speed_first import ROOT, validate_sized, size_check
from benchmark_effort8 import LibFLAC, library, sha, command_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--exact-r7', action='store_true')
    args = parser.parse_args()
    assert not args.report.exists() and not args.work.exists(), 'Preserve prior evidence'
    identity = json.loads(args.identity.read_text())
    cli = (ROOT / identity['cli']['path']).resolve()
    assert sha(cli) == identity['cli']['sha256']
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest
    args.work.mkdir(parents=True)
    evidence = ROOT / 'validation/evidence'
    prior = json.loads((evidence / 'speed-first-revision7-quality.json').read_text())
    r7 = {c['name']: c['encoded_sha256'] for group in prior['sets'] for c in group['cases']}
    ref = LibFLAC(library(None))
    opts = SimpleNamespace(flac=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe',
                           ffmpeg='ffmpeg', timeout=1800)
    report = dict(status='running', cli_sha256=sha(cli), identity_sha256=sha(args.identity),
                  script_sha256=sha(Path(__file__)), exact_r7_required=args.exact_r7,
                  quality_anchor='e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743',
                  sets=[], scope='Correctness and fixed quality budgets; no timing measurements')

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')

    try:
        for source in ['speed-first-revision3-holdout-gate.json',
                       'speed-first-revision3-holdout2-gate-general-depth.json']:
            old = json.loads((evidence / source).read_text())
            assert old['status'] == 'pass'
            group = dict(source_report=source, source_sha256=sha(evidence / source), cases=[])
            report['sets'].append(group)
            for case in old['cases']:
                assert sha(ROOT / case['path']) == case['pcm_sha256']
                baseline = Path(case['codecs']['baseline']['command'][3])
                assert sha(baseline) == case['codecs']['baseline']['encoded_sha256']
                output = args.work / (case['name'] + '.flac')
                command = command_for('candidate', cli, case, output.resolve(), False, 1)
                subprocess.run(command, capture_output=True, check=True, timeout=1800)
                checked = validate_sized(output, case, ref, opts)
                equal = checked['encoded_sha256'] == r7[case['name']]
                row = dict(name=case['name'], command=command, **checked,
                           revision7_bytes_identical=equal,
                           size_budget=size_check(baseline.stat().st_size, output.stat().st_size, 1.03))
                group['cases'].append(row)
                save()
                assert not args.exact_r7 or equal, ('r7 bitstream changed', case['name'])
            group['aggregate_size_budget'] = size_check(
                sum(c['size_budget']['baseline_bytes'] for c in group['cases']),
                sum(c['size_budget']['candidate_bytes'] for c in group['cases']), 1.01)
            group['status'] = 'pass' if group['aggregate_size_budget']['passed'] and all(
                c['size_budget']['passed'] for c in group['cases']) else 'failed_budget'
            save()
        assert all(g['status'] == 'pass' for g in report['sets'])
        assert sha(cli) == report['cli_sha256']
        for name, digest in identity['sources'].items():
            assert sha(ROOT / name) == digest
        report.update(status='pass', case_count=sum(len(g['cases']) for g in report['sets']))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
