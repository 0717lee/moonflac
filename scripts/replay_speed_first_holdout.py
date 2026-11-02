"""Confirm the final post-format executable reproduces every frozen gate output."""
import json
from pathlib import Path
from types import SimpleNamespace
from benchmark_speed_first import ROOT, validate_sized
from benchmark_effort8 import LibFLAC, library, sha, command_for, measure


def main():
    evidence = ROOT / 'validation/evidence'
    identity = json.loads((evidence / 'speed-first-candidate-revision3.json').read_text())
    cli = ROOT / identity['cli']['path']
    assert sha(cli) == identity['cli']['sha256']
    work = ROOT / 'validation/cache/speed-first-final-holdout'
    work.mkdir(parents=True, exist_ok=False)
    report_path = evidence / 'speed-first-final-holdout-replay.json'
    assert not report_path.exists()
    report = dict(status='running', cli_sha256=sha(cli), script_sha256=sha(Path(__file__)), cases=[])
    ref = LibFLAC(library(None))
    opts = SimpleNamespace(flac=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe',
                           ffmpeg='ffmpeg', timeout=1800)
    try:
        for source in ['speed-first-revision3-holdout-gate.json',
                       'speed-first-revision3-holdout2-gate-general-depth.json']:
            old = json.loads((evidence / source).read_text())
            assert old['status'] == 'pass'
            for case in old['cases']:
                output = work / (case['name'] + '.flac')
                command = command_for('candidate', cli, case, output, False, 1)
                run = measure(command, opts.timeout)
                checked = validate_sized(output, case, ref, opts)
                assert checked['encoded_sha256'] == case['codecs']['candidate']['encoded_sha256']
                report['cases'].append(dict(name=case['name'], source_report=source,
                    command=command, **run, **checked, preformat_bytes_identical=True))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
        assert sha(cli) == report['cli_sha256']
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
