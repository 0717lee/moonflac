"""Sealed nonzero-background pulse quality regression; no TEMP dependencies.

prepare: generate 2 exact review reproducers and 30 predeclared variants, then
encode/decode the accepted baseline. run: evaluate a separately built candidate.
Inputs and budgets are frozen before candidate results and are never retuned.
"""
import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path

from validate_encoder import LibFLAC, library, version

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'validation/fixtures/speed-first-pulses'
WORK = ROOT / 'validation/cache/speed-first-pulses'
EVIDENCE = ROOT / 'validation/evidence'
MANIFEST = EVIDENCE / 'speed-first-pulses-manifest.json'
BASELINE_REPORT = EVIDENCE / 'speed-first-pulses-baseline.json'
BASELINE_SHA = 'e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743'
SEED = 202609291339
ORIGINALS = {
    'tail-4096-255': '1cec872a5e22bd51ac7f77c6dda441ad4bee0453ee56d47f0b6d75de18d9a013',
    'tail-4096-256': '3bac8c64770c482f5e0c17d1974b012a9bbadfecf3c52e18dc06c92da0bdf0ab',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def pack(values, bits):
    return b''.join(value.to_bytes((bits + 7) // 8, 'little', signed=True) for value in values)


def original_inputs():
    # Reproduce the reviewer's single sequential RNG, including all preceding
    # boundary cases, so both original raw byte hashes remain exact.
    rng = random.Random(SEED)

    def generated(frames, bits, channels):
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        return pack([rng.choice([lo, hi]) if (i + c * 19) % 113 == 0 else ((i + c) % 5) - 2
                     for i in range(frames) for c in range(channels)], bits)

    for length in [1, 15, 17, 64, 254, 255, 256, 257, 258]:
        for bits, channels in [(16, 1), (25, 4), (32, 8)]:
            generated(length, bits, channels)
    generated(1025, 25, 8)
    generated(1061, 25, 8)
    return {f'tail-4096-{tail}': generated(4096 + tail, 25, 8) for tail in [255, 256]}


def fixtures():
    cases = []
    FIXTURES.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    def add(name, raw, bits, channels, block, variable, provenance, directory=WORK, **parameters):
        path = directory / (name + '.raw')
        if path.exists():
            assert path.read_bytes() == raw, 'never overwrite changed fixture: ' + name
        else:
            path.write_bytes(raw)
        cases.append(dict(name=name, path=path.relative_to(ROOT).as_posix(), bits=bits, channels=channels,
                          samples=len(raw) // (((bits + 7) // 8) * channels), rate=48000, block=block,
                          variable=variable, effort=8, pcm_bytes=len(raw), pcm_sha256=sha(path),
                          pcm_md5=hashlib.md5(raw).hexdigest(), provenance=provenance, **parameters))

    for name, raw in original_inputs().items():
        assert hashlib.sha256(raw).hexdigest() == ORIGINALS[name], name
        add(name, raw, 25, 8, 4096, False,
            'Exact review independent-02 reproducer; original Python RNG sequence reproduced in this script',
            FIXTURES, original_review_failure=True)
    formats = [(16, 1), (25, 2), (32, 8)]
    for amplitude_index, amplitude in enumerate([2, 7, 31]):
        for interval_index, interval in enumerate([7, 17, 53, 113, 257]):
            bits, channels = formats[(amplitude_index + interval_index) % len(formats)]
            block = [1024, 4096, 8192][(amplitude_index + 2 * interval_index) % 3]
            tail = [0, 37, 255, 256, 257][interval_index]
            seed = SEED + 1000 + amplitude_index * 100 + interval_index
            rng = random.Random(seed)
            lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
            values = []
            for i in range(block + tail):
                for channel in range(channels):
                    value = rng.choice([lo, hi]) if (i + channel * 19) % interval == 0 else (
                        (1 if (i + channel) % 2 else -1) * (1 + (i + channel * 3) % amplitude))
                    values.append(value)
            raw = pack(values, bits)
            for variable in [False, True]:
                name = f'background{amplitude}-pulse{interval}-{bits}bit-{channels}ch-' + ('variable' if variable else 'fixed')
                add(name, raw, bits, channels, block, variable,
                    'Independent deterministic Python signed nonzero background with full-scale pulses',
                    amplitude=amplitude, interval=interval, seed=seed, tail=tail)
    assert len(cases) == 32
    return cases


def command(cli, case, output):
    args = [str(cli), 'encode', str(ROOT / case['path']), str(output), '--raw', '--sample-rate', str(case['rate']),
            '--channels', str(case['channels']), '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', '8']
    if case['variable']:
        args.append('--variable-block')
    return args


def validate(path, case, ref, flac):
    raw = (ROOT / case['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == case['pcm_sha256']
    width = (case['bits'] + 7) // 8
    expected = [int.from_bytes(raw[i:i + width], 'little', signed=True) for i in range(0, len(raw), width)]
    props, actual = ref.decode(path)
    assert props == (case['channels'], case['bits'], case['rate']) and actual == expected, 'independent PCM mismatch'
    data = path.read_bytes()
    assert data[:4] == b'fLaC' and data[4] & 127 == 0
    assert data[26:42] == hashlib.md5(raw).digest(), 'STREAMINFO MD5 differs from original Python bytes'
    crc_command = [str(flac), '--silent', '-t', str(path)]
    check = subprocess.run(crc_command, capture_output=True, timeout=180)
    check.check_returncode()
    return dict(encoded_sha256=sha(path), encoded_bytes=len(data), independent_pcm='libFLAC exact',
                streaminfo_md5='Python hashlib exact', crc_md5='libFLAC -t pass', crc_command=crc_command)


def prepare(args):
    assert sha(args.baseline) == BASELINE_SHA
    assert not MANIFEST.exists() and not BASELINE_REPORT.exists(), 'Preserve sealed fixtures and baseline evidence'
    cases = fixtures()
    manifest = dict(task='speed-first pulse partition review independent-02', seed=SEED,
                    generator_sha256=sha(Path(__file__)), cases=cases, inputs_frozen_before_candidate=True,
                    size_budget=dict(per_case=1.03, aggregate=1.01),
                    scope='2 exact review inputs + 15 independent nonzero-background PCM variants, each fixed and variable blocking; no timing claim')
    save(MANIFEST, manifest)
    ref = LibFLAC(library(args.libflac))
    report = dict(status='running', baseline_sha256=sha(args.baseline), manifest_sha256=sha(MANIFEST),
                  libflac=version(ref), cases=[])
    try:
        for case in cases:
            output = WORK / (case['name'] + '-baseline.flac')
            cmd = command(args.baseline, case, output)
            subprocess.run(cmd, capture_output=True, check=True, timeout=180)
            report['cases'].append(dict(name=case['name'], output=output.relative_to(ROOT).as_posix(),
                                        command=cmd, **validate(output, case, ref, args.flac)))
            save(BASELINE_REPORT, report)
            print('baseline', case['name'], flush=True)
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save(BASELINE_REPORT, report)


def run(args):
    assert args.candidate and args.report
    assert not args.report.exists(), 'Preserve prior quality outcomes'
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    baseline = json.loads(BASELINE_REPORT.read_text(encoding='utf-8'))
    assert baseline['status'] == 'pass' and baseline['baseline_sha256'] == BASELINE_SHA
    assert baseline['manifest_sha256'] == sha(MANIFEST)
    frozen = {row['name']: row for row in baseline['cases']}
    ref = LibFLAC(library(args.libflac))
    report = dict(status='running', candidate_sha256=sha(args.candidate), baseline_sha256=BASELINE_SHA,
                  manifest_sha256=sha(MANIFEST), baseline_report_sha256=sha(BASELINE_REPORT),
                  script_sha256=sha(Path(__file__)), libflac=version(ref), cases=[],
                  scope='Complete pre-frozen quality matrix; no controlled performance claim')
    try:
        for case in manifest['cases']:
            old = frozen[case['name']]
            assert sha(ROOT / old['output']) == old['encoded_sha256']
            output = WORK / (case['name'] + '-' + args.report.stem + '.flac')
            cmd = command(args.candidate, case, output)
            subprocess.run(cmd, capture_output=True, check=True, timeout=180)
            checked = validate(output, case, ref, args.flac)
            size_pass = checked['encoded_bytes'] * 100 <= old['encoded_bytes'] * 103
            row = dict(case, command=cmd, **checked, baseline_bytes=old['encoded_bytes'],
                       baseline_encoded_sha256=old['encoded_sha256'],
                       size_ratio=checked['encoded_bytes'] / old['encoded_bytes'], size_budget_pass=size_pass,
                       baseline_bytes_identical=checked['encoded_sha256'] == old['encoded_sha256'])
            report['cases'].append(row)
            save(args.report, report)
            print('candidate', case['name'], 'size_pass', size_pass, flush=True)
        old_total = sum(row['baseline_bytes'] for row in report['cases'])
        new_total = sum(row['encoded_bytes'] for row in report['cases'])
        assert len(report['cases']) == 32
        report.update(case_count=32, aggregate=dict(baseline_bytes=old_total, candidate_bytes=new_total,
                      ratio=new_total / old_total, passed=new_total * 100 <= old_total * 101),
                      above_three_percent=[row['name'] for row in report['cases'] if not row['size_budget_pass']])
        assert sha(args.candidate) == report['candidate_sha256'], 'candidate binary changed'
        report['status'] = 'pass' if report['aggregate']['passed'] and not report['above_three_percent'] else 'failed_budget'
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save(args.report, report)
    if report['status'] != 'pass':
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--baseline', type=Path, default=ROOT / '_build/speed-first/accepted-baseline.exe')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--libflac')
    parser.add_argument('--flac', type=Path, default=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else run)(args)


if __name__ == '__main__':
    main()
