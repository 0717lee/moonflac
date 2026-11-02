"""Replay both retained quality sets for exact partition search, without retuning.

Long-frame output may improve under the exact partition rule. Record revision3
byte equality as an observation, not a gate. Times are diagnostics, not benchmarks.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from benchmark_speed_first import ROOT, validate_sized, size_check
from benchmark_effort8 import LibFLAC, library, sha, command_for, measure


def main():
    evidence = ROOT / 'validation/evidence'
    identity = json.loads((evidence / 'speed-first-candidate-revision7.json').read_text())
    cli = ROOT / identity['cli']['path']
    assert sha(cli) == identity['cli']['sha256'] == '71be364ccf233d29d5a3327ddd78ba7ad076bdb4c6fcc34b11a00d0a482041a9'
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest
    destination = evidence / 'speed-first-revision7-quality.json'
    assert not destination.exists()
    work = ROOT / 'validation/cache/speed-first-revision7-quality'
    work.mkdir(parents=True, exist_ok=False)
    ref = LibFLAC(library(None))
    opts = SimpleNamespace(flac=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe',
                           ffmpeg='ffmpeg', timeout=1800)
    report = dict(status='running', cli_sha256=sha(cli), sets=[], script_sha256=sha(Path(__file__)),
                  identity_sha256=sha(evidence / 'speed-first-candidate-revision7.json'),
                  scope='Both retained quality sets; independent PCM/CRC/MD5 and empirical 3%/1% size budgets; no timing claim',
                  revision3_byte_equality_is_required=False)

    def save():
        destination.write_text(json.dumps(report, indent=2)+'\n')

    try:
        for source in ['speed-first-revision3-holdout-gate.json',
                       'speed-first-revision3-holdout2-gate-general-depth.json']:
            old = json.loads((evidence / source).read_text())
            assert old['status'] == 'pass'
            group = dict(source_report=source, source_sha256=sha(evidence/source), cases=[])
            report['sets'].append(group)
            for case in old['cases']:
                assert sha(ROOT/case['path']) == case['pcm_sha256']
                baseline = Path(case['codecs']['baseline']['command'][3])
                assert sha(baseline) == case['codecs']['baseline']['encoded_sha256']
                output = work / (case['name']+'.flac')
                command = command_for('candidate', cli, case, output, False, 1)
                measured = measure(command, opts.timeout)
                checked = validate_sized(output, case, ref, opts)
                unchanged = checked['encoded_sha256'] == case['codecs']['candidate']['encoded_sha256']
                no_short_blocks = case['block'] > 256 and (case['samples'] % case['block'] == 0 or case['samples'] % case['block'] > 256)
                row = dict(name=case['name'], command=command, **measured, **checked,
                           revision3_bytes_identical=unchanged, no_short_blocks=no_short_blocks,
                           size_budget=size_check(baseline.stat().st_size, output.stat().st_size, 1.03),
                           file_to_pcm_ratio=output.stat().st_size/case['pcm_bytes'],
                           payload_to_pcm_ratio=checked['payload_bytes']/case['pcm_bytes'])
                group['cases'].append(row)
                save()
            group['aggregate_size_budget'] = size_check(
                sum(c['size_budget']['baseline_bytes'] for c in group['cases']),
                sum(c['size_budget']['candidate_bytes'] for c in group['cases']), 1.01)
            group['status'] = 'pass' if group['aggregate_size_budget']['passed'] and all(c['size_budget']['passed'] for c in group['cases']) else 'failed_budget'
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
