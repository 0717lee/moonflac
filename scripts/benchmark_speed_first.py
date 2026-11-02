"""Speed-first encoder paired benchmarking with explicit compression budgets.

Uses the accepted effort8 helpers without modifying historical scripts/evidence.
The baseline/candidate bitstreams may differ; every run still requires exact
independent PCM, valid CRC/MD5 and within-codec deterministic output.

run: one warmup + six balanced paired rounds, CLI or --core.
reference-only: retain all -0/-5/-8/-8 -e -p observations and select nearest
candidate payload size by absolute distance, not by advantageous timing.
No downloads or automatic fixture generation.
"""
import argparse
import hashlib
import json
import math
import platform
import shutil
import struct
import subprocess
from pathlib import Path

import psutil
from benchmark_effort8 import ORDERS, timed, validate, measure, command_for, summary, sha, save
from validate_encoder import LibFLAC, library, version
from packetized_flac import wrap_file

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'validation/cache/speed-first-benchmark'
REFERENCE_CONFIGS = [
    ('libflac-0', ['-0']),
    ('libflac-5', ['-5']),
    ('libflac-8', ['-8']),
    ('libflac-8-exhaustive', ['-8', '-e', '-p']),
]


def load_cases(path, match=''):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    cases = [dict(c) for c in manifest['cases'] if match in c['name']]
    assert cases and len({c['name'] for c in cases}) == len(cases)
    for case in cases:
        case.setdefault('pcm_bytes', case['samples'] * case['channels'] * ((case['bits'] + 7) // 8))
        assert case['samples'] > 0 and case['pcm_bytes'] > 0
        assert case.get('effort', 8) == 8, 'This comparison is fixed effort8'
        case['effort'] = 8
    return cases


def payload_size(path):
    data = path.read_bytes()
    assert data[:4] == b'fLaC', 'native FLAC required for payload accounting'
    cursor = 4
    while True:
        assert cursor + 4 <= len(data), 'truncated metadata'
        last = data[cursor] & 128
        length = int.from_bytes(data[cursor + 1:cursor + 4], 'big')
        cursor += 4 + length
        assert cursor <= len(data), 'truncated metadata payload'
        if last:
            return len(data) - cursor, cursor


def validate_sized(output, case, ref, args):
    explicit_large_transport = getattr(args, 'large_frame_transport', False)
    if explicit_large_transport:
        assert case['block'] in (32768, 65535), '--large-frame-transport requires the declared large-frame group'
    if case['bits'] in (16, 24, 32) and not explicit_large_transport:
        result = validate(output, case, ref, args)
    else:
        result = validate_general_depth(output, case, ref, args)
    payload, metadata = payload_size(output)
    assert payload > 0, 'nonempty input must emit frames'
    result.update(payload_bytes=payload, metadata_bytes=metadata)
    return result


def validate_general_depth(output, case, ref, args):
    bits = case['bits']
    assert 4 <= bits <= 32
    width = (bits + 7) // 8
    raw = (ROOT / case['path']).read_bytes()
    assert len(raw) == case['samples'] * case['channels'] * width
    expected = [int.from_bytes(raw[i:i + width], 'little', signed=True)
                for i in range(0, len(raw), width)]
    assert all(-(1 << (bits - 1)) <= value < (1 << (bits - 1)) for value in expected)
    properties, pcm = ref.decode(output)
    assert properties == (case['channels'], bits, case['rate']), properties
    assert pcm == expected, 'libFLAC PCM mismatch'
    subprocess.run([str(args.flac), '-t', '-s', str(output)], check=True,
                   capture_output=True, timeout=args.timeout)
    shift = 32 - bits

    def decode(path):
        return subprocess.run([str(args.ffmpeg), '-v', 'error', '-i', str(path),
                               '-map', '0:a:0', '-c:a', 'pcm_s32le', '-f', 's32le', 'pipe:1'],
                              capture_output=True, timeout=args.timeout)

    def exact(data):
        if len(data) != len(expected) * 4:
            return False
        values = [v[0] for v in struct.iter_unpack('<i', data)]
        # Require exact left alignment as well as original-depth integer equality;
        # right-shifting alone must not conceal unexpected low-order bits.
        return all((value & ((1 << shift) - 1)) == 0 and value >> shift == original
                   for value, original in zip(values, expected))

    process = decode(output)
    transport = 'native FLAC'
    extra = {}
    if case['block'] == 65535 or getattr(args, 'large_frame_transport', False):
        # This transport is selected by maximum block size or the explicit
        # large-frame-group CLI flag before inspecting the raw result. It is
        # never a failure-triggered retry for arbitrary input streams.
        extra['ffmpeg_native'] = dict(bytes=len(process.stdout),
            exact_pcm=process.returncode == 0 and exact(process.stdout),
            pcm_sha256=hashlib.sha256(process.stdout).hexdigest(),
            returncode=process.returncode, stderr=process.stderr.decode(errors='replace'))
        wrapped = output.with_suffix('.ffmpeg.oga')
        extra['ffmpeg_packetization'] = wrap_file(output, wrapped, args.flac)
        process = decode(wrapped)
        transport = 'Ogg carrying unchanged frames; boundaries from official libFLAC analysis'
    process.check_returncode()
    assert exact(process.stdout), 'FFmpeg full PCM or left-alignment mismatch'
    return dict(encoded_sha256=sha(output), encoded_bytes=output.stat().st_size,
                libflac_pcm='exact', ffmpeg_pcm='exact', ffmpeg_transport=transport,
                ffmpeg_format='pcm_s32le', ffmpeg_integer_right_shift=shift,
                ffmpeg_explicit_large_frame_transport=getattr(args, 'large_frame_transport', False),
                ffmpeg_low_bits_zero_required=True,
                source_raw_format=f'signed little endian, {width} bytes per sample, {bits} valid bits',
                flac_md5_crc='pass', **extra)


def size_check(baseline, candidate, limit):
    # Integer comparison avoids floating-point tolerance changing the budget.
    numerator = round(limit * 100)
    return dict(baseline_bytes=baseline, candidate_bytes=candidate,
                ratio=candidate / baseline, limit=limit,
                passed=candidate * 100 <= baseline * numerator)


def run(args):
    if args.rounds < 6 or args.rounds % 6:
        raise ValueError('--rounds must be a positive multiple of six, at least six')
    if args.min_core_seconds <= 0 or args.max_batch < 1:
        raise ValueError('invalid calibration limits')
    if args.report.exists():
        raise FileExistsError(f'Preserve prior report: {args.report}')
    ref = LibFLAC(library(args.libflac))
    binaries = {k: v.resolve() for k, v in [('baseline', args.baseline),
                  ('candidate', args.candidate), ('libflac', args.flac)]}
    allowed = psutil.Process().cpu_affinity()
    cpu = args.cpu if args.cpu is not None else allowed[len(allowed) // 2]
    if cpu not in allowed:
        raise ValueError(f'CPU {cpu} is not available: {allowed}')
    psutil.Process().cpu_affinity([cpu])
    cases = load_cases(args.manifest, args.match)
    assert cases, 'no cases selected'
    report = dict(status='running', mode='core' if args.core else 'cli', cases=[],
                  platform=platform.platform(), processor=platform.processor(), logical_cpu=cpu,
                  reference=version(ref), ffmpeg_version=subprocess.check_output([str(args.ffmpeg), '-version'], text=True).splitlines()[0],
                  manifest_sha256=sha(args.manifest), script_sha256=sha(__file__),
                  reused_helper_sha256=sha(ROOT / 'scripts/benchmark_effort8.py'),
                  packetizer_sha256=sha(ROOT / 'scripts/packetized_flac.py'),
                  binaries={k: dict(path=str(v), sha256=sha(v)) for k, v in binaries.items()},
                  source_identities={k: json.loads(p.read_text(encoding='utf-8')) for k, p in
                                     [('baseline', args.baseline_identity), ('candidate', args.candidate_identity)] if p},
                  protocol=dict(warmup_rounds=1, measured_rounds=args.rounds, orders=ORDERS,
                                core_internal_warmups_per_process=1 if args.core else 0,
                                memory='whole process peak working set on Windows; sampled RSS elsewhere; includes core input/expected output',
                                reference_timing='libFLAC CLI wall time, not in-process core',
                                calibration='both codecs batch=1; common fixed batch targets fastest pilot; capped explicitly',
                                independent_validation='after each timed run; warm-cache, no cold-cache claims'))
    report['protocol']['maximum_block_ffmpeg_transport'] = 'Always packetize original frames using official analysis; record raw-path result separately. See effort8-ffmpeg-parser.json.'
    report['protocol']['explicit_large_frame_transport'] = getattr(args, 'large_frame_transport', False)
    if getattr(args, 'large_frame_transport', False):
        report['protocol']['large_frame_transport_evidence'] = 'speed-first-ffmpeg-32768.json; predeclared flag, no failure-triggered fallback'
    report['size_budget'] = dict(per_case_max_ratio=1.03, collection_max_ratio=1.01, basis='total native FLAC file bytes')
    WORK.mkdir(parents=True, exist_ok=True)
    save(args.report, report)
    try:
        for case in cases:
            assert sha(ROOT / case['path']) == case['pcm_sha256'], 'input identity changed'
            entry = dict(case, calibration=[], batch=1, runs={k: [] for k in binaries}, timeline=[])
            report['cases'].append(entry)
            outputs = {k: WORK / f'{args.report.stem}-{case["name"]}-{k}.flac' for k in binaries}
            if args.core:
                for codec in ['baseline', 'candidate']:
                    pilot = timed(codec, binaries, case, outputs[codec], args, 1)
                    pilot.update(codec=codec, **validate_sized(outputs[codec], case, ref, args))
                    entry['calibration'].append(pilot)
                fastest = min(r['seconds'] for r in entry['calibration'])
                entry['batch'] = min(args.max_batch, max(1, math.ceil(args.min_core_seconds / max(fastest, 1e-9))))
                entry['calibration_capped'] = entry['batch'] == args.max_batch and fastest * entry['batch'] < args.min_core_seconds
            for repetition in range(-1, args.rounds):
                order = ORDERS[repetition % 6]
                for position, codec in enumerate(order):
                    load = psutil.cpu_percent(interval=.05, percpu=True)
                    result = timed(codec, binaries, case, outputs[codec], args, entry['batch'])
                    result.update(repetition=repetition, warmup=repetition < 0, position=position,
                                  host_cpu_before=load, **validate_sized(outputs[codec], case, ref, args))
                    entry['runs'][codec].append(result)
                    entry['timeline'].append(dict(repetition=repetition, position=position, codec=codec))
                    save(args.report, report)
            entry['bitstream_unchanged'] = outputs['baseline'].read_bytes() == outputs['candidate'].read_bytes()
            entry['summary'] = {}
            for codec, runs in entry['runs'].items():
                measured = [r for r in runs if not r['warmup']]
                assert len({r['encoded_sha256'] for r in runs}) == 1, 'nondeterministic output'
                stats = summary([r['seconds'] for r in measured])
                entry['summary'][codec] = dict(seconds=stats, encoded_bytes=runs[0]['encoded_bytes'],
                    payload_bytes=runs[0]['payload_bytes'], metadata_bytes=runs[0]['metadata_bytes'],
                    file_to_pcm_ratio=runs[0]['encoded_bytes'] / case['pcm_bytes'],
                    payload_to_pcm_ratio=runs[0]['payload_bytes'] / case['pcm_bytes'],
                    peak_process_bytes=max(r['peak_process_bytes'] for r in runs),
                    sample_frames_per_second=case['samples'] / stats['median'],
                    pcm_bytes_per_second=case['pcm_bytes'] / stats['median'])
            before = entry['runs']['baseline'][1:]
            after = entry['runs']['candidate'][1:]
            entry['paired_differences_seconds'] = [b['seconds'] - a['seconds'] for b, a in zip(before, after)]
            entry['paired_reduction_percent'] = [100 * (b['seconds'] - a['seconds']) / b['seconds'] for b, a in zip(before, after)]
            entry['paired_difference_summary'] = summary(entry['paired_differences_seconds'])
            b = entry['summary']['baseline']['seconds']['median']
            c = entry['summary']['candidate']['seconds']['median']
            entry['median_reduction_percent'] = 100 * (b - c) / b
            entry['paired_improvement_rounds'] = sum(x > 0 for x in entry['paired_differences_seconds'])
            entry['size_check'] = size_check(entry['summary']['baseline']['encoded_bytes'], entry['summary']['candidate']['encoded_bytes'], 1.03)
            entry['payload_size_ratio'] = entry['summary']['candidate']['payload_bytes'] / entry['summary']['baseline']['payload_bytes']
            save(args.report, report)
            print(case['name'], entry['median_reduction_percent'], entry['paired_difference_summary'], flush=True)
        totals = {k: sum(c['summary'][k]['seconds']['median'] for c in report['cases']) for k in binaries}
        worst = min(report['cases'], key=lambda c: c['median_reduction_percent'])
        file_totals = {k: sum(c['summary'][k]['encoded_bytes'] for c in report['cases']) for k in binaries}
        payload_totals = {k: sum(c['summary'][k]['payload_bytes'] for c in report['cases']) for k in binaries}
        pcm_total = sum(c['pcm_bytes'] for c in report['cases'])
        budget = size_check(file_totals['baseline'], file_totals['candidate'], 1.01)
        violations = [c['name'] for c in report['cases'] if not c['size_check']['passed']]
        report.update(status='pass' if budget['passed'] and not violations else 'failed_budget',
                      all_cases_completed=True, budget_violations=violations, collection_size_check=budget,
                      collection_sizes={k: dict(file_bytes=file_totals[k], payload_bytes=payload_totals[k],
                            file_to_pcm_ratio=file_totals[k]/pcm_total, payload_to_pcm_ratio=payload_totals[k]/pcm_total) for k in binaries},
                      fixed_set_sum_medians_seconds=totals,
                      fixed_set_reduction_percent=100 * (totals['baseline'] - totals['candidate']) / totals['baseline'],
                      worst_case=dict(name=worst['name'], median_reduction_percent=worst['median_reduction_percent']))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(args.report, report)
    if report['status'] != 'pass':
        raise SystemExit(1)


def reference_only(args):
    if args.rounds < 6 or args.rounds % 6:
        raise ValueError('--rounds must be a multiple of six, at least six')
    if args.report.exists():
        raise FileExistsError(args.report)
    help_text = subprocess.check_output([str(args.flac), '--help'], text=True)
    for option in ['--exhaustive-model-search', '--qlp-coeff-precision-search']:
        assert option in help_text, 'reference encoder does not advertise ' + option
    original = json.loads(args.candidate_report.read_text(encoding='utf-8'))
    assert original.get('all_cases_completed') and original.get('status') in ['pass', 'failed_budget']
    assert original['manifest_sha256'] == sha(args.manifest), 'candidate report uses another manifest'
    cases = load_cases(args.manifest, args.match)
    accepted = {c['name']: c for c in original['cases']}
    assert all(c['name'] in accepted for c in cases), 'candidate cases missing'
    available = psutil.Process().cpu_affinity()
    cpu = args.cpu if args.cpu is not None else available[len(available) // 2]
    assert cpu in available
    psutil.Process().cpu_affinity([cpu])
    WORK.mkdir(parents=True, exist_ok=True)
    ref = LibFLAC(library(args.libflac))
    labels = [name for name, _ in REFERENCE_CONFIGS]
    settings = dict(REFERENCE_CONFIGS)
    orders = [labels[i % len(labels):] + labels[:i % len(labels)] for i in range(args.rounds)]
    report = dict(status='running', mode='reference-only-cli', cases=[],
                  platform=platform.platform(), logical_cpu=cpu, reference=version(ref),
                  script_sha256=sha(Path(__file__)), helper_sha256=sha(ROOT / 'scripts/benchmark_effort8.py'),
                  packetizer_sha256=sha(ROOT / 'scripts/packetized_flac.py'),
                  manifest_sha256=sha(args.manifest), candidate_report_sha256=sha(args.candidate_report),
                  flac_binary_sha256=sha(args.flac), available_options=help_text,
                  configurations=settings, measured_orders=orders,
                  protocol='1 warmup + balanced 6-round multiples; four reference configurations rotate positions; full results retained',
                  limitations=['Four configurations in six rounds have position counts differing by at most one.',
                               'Reference timings are new observations, not paired with the earlier candidate measurement.',
                               'Closest size is absolute payload-byte difference; it is not a matched-quality speed claim.'])
    report['explicit_large_frame_transport'] = getattr(args, 'large_frame_transport', False)
    save(args.report, report)
    try:
        for case in cases:
            assert sha(ROOT / case['path']) == case['pcm_sha256']
            old = accepted[case['name']]
            assert old['pcm_sha256'] == case['pcm_sha256']
            candidate_size = old['summary']['candidate']['payload_bytes']
            entry = dict(case, candidate_summary=old['summary']['candidate'],
                         runs={name: [] for name in labels}, timeline=[])
            report['cases'].append(entry)
            for repetition in range(-1, args.rounds):
                order = labels if repetition < 0 else orders[repetition]
                for position, label in enumerate(order):
                    output = WORK / f'{args.report.stem}-{case["name"]}-{label}.flac'
                    command = command_for('libflac', args.flac, case, output, False, 1)
                    command[1:2] = settings[label]
                    load = psutil.cpu_percent(interval=.05, percpu=True)
                    result = measure(command, args.timeout)
                    result.update(seconds=result['wall_seconds'], command=command, repetition=repetition,
                                  warmup=repetition < 0, position=position, host_cpu_before=load,
                                  **validate_sized(output, case, ref, args))
                    entry['runs'][label].append(result)
                    entry['timeline'].append(dict(repetition=repetition, position=position, codec=label))
                    save(args.report, report)
            entry['summary'] = {}
            for label, runs in entry['runs'].items():
                assert len({r['encoded_sha256'] for r in runs}) == 1, 'reference output is nondeterministic'
                stats = summary([r['seconds'] for r in runs if not r['warmup']])
                entry['summary'][label] = dict(seconds=stats, encoded_bytes=runs[0]['encoded_bytes'],
                    payload_bytes=runs[0]['payload_bytes'], metadata_bytes=runs[0]['metadata_bytes'],
                    file_to_pcm_ratio=runs[0]['encoded_bytes'] / case['pcm_bytes'],
                    payload_to_pcm_ratio=runs[0]['payload_bytes'] / case['pcm_bytes'],
                    peak_process_bytes=max(r['peak_process_bytes'] for r in runs),
                    sample_frames_per_second=case['samples'] / stats['median'],
                    pcm_bytes_per_second=case['pcm_bytes'] / stats['median'],
                    absolute_candidate_payload_distance=abs(runs[0]['payload_bytes'] - candidate_size))
            nearest = min(v['absolute_candidate_payload_distance'] for v in entry['summary'].values())
            entry['closest_payload_configurations'] = [k for k, v in entry['summary'].items()
                                                       if v['absolute_candidate_payload_distance'] == nearest]
            save(args.report, report)
            print(case['name'], entry['closest_payload_configurations'], flush=True)
        report['fixed_set'] = {label: dict(
            sum_median_seconds=sum(c['summary'][label]['seconds']['median'] for c in report['cases']),
            file_bytes=sum(c['summary'][label]['encoded_bytes'] for c in report['cases']),
            payload_bytes=sum(c['summary'][label]['payload_bytes'] for c in report['cases'])) for label in labels}
        candidate_total = sum(c['candidate_summary']['payload_bytes'] for c in report['cases'])
        distance = {label: abs(values['payload_bytes'] - candidate_total) for label, values in report['fixed_set'].items()}
        report['candidate_total_payload_bytes'] = candidate_total
        report['closest_collection_payload_configurations'] = [label for label, value in distance.items() if value == min(distance.values())]
        report.update(status='pass', all_cases_completed=True)
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(args.report, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    paired = actions.add_parser('run')
    reference = actions.add_parser('reference-only')
    for command in [paired, reference]:
        command.add_argument('--manifest', type=Path, required=True)
        command.add_argument('--report', type=Path, required=True)
        command.add_argument('--flac', type=Path, default=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
        command.add_argument('--ffmpeg', type=Path, default=Path(shutil.which('ffmpeg') or 'ffmpeg'))
        command.add_argument('--libflac')
        command.add_argument('--rounds', type=int, default=6)
        command.add_argument('--timeout', type=float, default=1800)
        command.set_defaults(match='')
        command.add_argument('--cpu', type=int)
        command.add_argument('--large-frame-transport', action='store_true',
                             help='Explicit unchanged-frame Ogg validation for a declared 32768/65535-frame group; records native FFmpeg result')
    paired.add_argument('--baseline', type=Path, required=True)
    paired.add_argument('--candidate', type=Path, required=True)
    paired.add_argument('--baseline-identity', type=Path, default=ROOT / 'validation/evidence/speed-first-baseline.json')
    paired.add_argument('--candidate-identity', type=Path, required=True)
    paired.add_argument('--core', action='store_true')
    paired.add_argument('--min-core-seconds', type=float, default=.5)
    paired.add_argument('--max-batch', type=int, default=256)
    reference.add_argument('--candidate-report', type=Path, required=True)
    args = parser.parse_args()
    (run if args.action == 'run' else reference_only)(args)


if __name__ == '__main__':
    main()
