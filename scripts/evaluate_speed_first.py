"""Exploratory speed/size point on the frozen twelve CLI inputs.

One candidate encode per case; historical accepted sizes are reused only after
input/parameter/output identity checks. Timing is diagnostic, not a paired
performance acceptance run. Independent PCM checks remain mandatory.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from benchmark_effort8 import ROOT, LibFLAC, library, sha, measure, command_for, validate


def payload(path):
    data = path.read_bytes()
    assert data[:4] == b'fLaC'
    cursor = 4
    while True:
        flag = data[cursor]
        length = int.from_bytes(data[cursor+1:cursor+4], 'big')
        cursor += 4 + length
        assert cursor <= len(data)
        if flag & 128:
            return len(data) - cursor


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True)
    p.add_argument('--cli', type=Path, default=ROOT/'_build/speed-first/candidate/native/release/build/cmd/moonflac/moonflac.exe')
    p.add_argument('--match', default='')
    p.add_argument('--report', type=Path, help='New evidence path; existing reports are never overwritten')
    args = p.parse_args()
    assert Path(args.label).name == args.label
    dest = ROOT/'validation/cache/speed-first-tuning'/args.label
    dest.mkdir(parents=True, exist_ok=False)
    report_path = args.report or ROOT/'validation/evidence'/f'speed-first-experiment-{args.label}.json'
    assert not report_path.exists()
    old = json.loads((ROOT/'validation/evidence/effort8-cli-benchmark.json').read_text())
    assert old['binaries']['candidate']['sha256'] == 'e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743'
    opts = SimpleNamespace(flac=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe', ffmpeg='ffmpeg', timeout=600)
    ref = LibFLAC(library(None))
    report = dict(status='running', label=args.label, method=__doc__, cases=[], script_sha256=sha(Path(__file__)),
                  cli_sha256=sha(args.cli), source_sha256={q.name:sha(q) for q in ROOT.glob('*.mbt') if not q.name.endswith(('_test.mbt','_wbtest.mbt'))})

    def save():
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    try:
        for case in old['cases']:
            if args.match not in case['name']:
                continue
            assert sha(ROOT/case['path']) == case['pcm_sha256']
            baseline = ROOT/'validation/cache/effort8-benchmark'/f"effort8-cli-benchmark-{case['name']}-candidate.flac"
            assert sha(baseline) == case['runs']['candidate'][0]['encoded_sha256']
            output = dest/(case['name']+'.flac')
            command = command_for('candidate', args.cli.resolve(), case, output, False, 1)
            measured = measure(command, 600)
            checked = validate(output, case, ref, opts)
            before, after = baseline.stat().st_size, output.stat().st_size
            row = dict(name=case['name'], bits=case['bits'], channels=case['channels'], samples=case['samples'], block=case['block'],
                       pcm_sha256=case['pcm_sha256'], pcm_bytes=case['pcm_bytes'], baseline_bytes=before, candidate_bytes=after,
                       full_file_ratio=after/before, baseline_payload=payload(baseline), candidate_payload=payload(output),
                       candidate_to_pcm=after/case['pcm_bytes'], seconds=measured['wall_seconds'], peak_process_bytes=measured['peak_process_bytes'],
                       command=command, independent=checked, within_case_budget=after*100 <= before*103)
            report['cases'].append(row)
            save()
            print(row['name'], row['full_file_ratio'], row['seconds'], flush=True)
        assert report['cases']
        before=sum(c['baseline_bytes'] for c in report['cases']);after=sum(c['candidate_bytes'] for c in report['cases'])
        report.update(status='pass', total_bytes_ratio=after/before, baseline_total_bytes=before, candidate_total_bytes=after,
                      total_seconds=sum(c['seconds'] for c in report['cases']), within_aggregate_budget=after*100<=before*101,
                      within_all_case_budgets=all(c['within_case_budget'] for c in report['cases']))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
