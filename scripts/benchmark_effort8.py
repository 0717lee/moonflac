"""Balanced effort-8 experiment; local cached fixtures only, no downloads.

Prepare once: python scripts/benchmark_effort8.py prepare --seconds 10
CLI: ... run --baseline old.exe --candidate new.exe --report cli.json
     --baseline-identity old-source.json --candidate-identity new-source.json
Core: ... run --core --baseline old-benchmark8.exe --candidate new-benchmark8.exe
      --report core.json --baseline-identity old-source.json
      --candidate-identity new-source.json

Run alone without other builds/stress jobs. Core paths must both be built from
the identical validation/benchmark8 harness. libFLAC measurements are always
CLI wall time and are never presented as an in-process core comparison.
"""
import argparse
import hashlib
import json
import math
import platform
import shutil
import statistics
import subprocess
import time
import wave
from pathlib import Path

import psutil
from validate_encoder import LibFLAC, library, packed, pcm_source, version
from packetized_flac import wrap_file

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'validation/cache/effort8-benchmark'
MANIFEST = WORK / 'inputs.json'
# All six permutations: each codec occupies each position twice; baseline and
# candidate precede one another exactly three times. Adjacent rounds reverse
# their relative order, including at repeated six-round boundaries.
ORDERS = [
    ['baseline', 'candidate', 'libflac'],
    ['candidate', 'libflac', 'baseline'],
    ['libflac', 'baseline', 'candidate'],
    ['libflac', 'candidate', 'baseline'],
    ['baseline', 'libflac', 'candidate'],
    ['candidate', 'baseline', 'libflac'],
]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def prepare(args):
    if args.seconds <= 0:
        raise ValueError('--seconds must be positive')
    WORK.mkdir(parents=True, exist_ok=True)
    input_dir = WORK / f'inputs-{args.seconds:g}s'
    input_dir.mkdir(parents=True, exist_ok=True)
    ref = LibFLAC(library(args.libflac))
    cases = []

    def add(name, raw, bits, channels, rate, provenance, source=None, block=4096):
        path = input_dir / (name + '.raw')
        path.write_bytes(raw)
        case = dict(name=name, path=str(path.relative_to(ROOT)), bits=bits,
                    channels=channels, rate=rate, block=block, effort=8,
                    samples=len(raw) // (channels * (bits // 8)),
                    pcm_sha256=sha(path), pcm_bytes=len(raw), provenance=provenance)
        if source:
            case.update(source=str(source.relative_to(ROOT)), source_sha256=sha(source))
        cases.append(case)

    for kind, bits, channels in [('noise', 16, 2), ('noise', 32, 2),
                                  ('ar', 24, 2), ('ar', 32, 2),
                                  ('ar', 24, 6), ('silence', 16, 2)]:
        count = math.ceil(args.seconds * 48000)
        add(f'{kind}-{bits}-{channels}', packed(pcm_source(bits, channels, count, kind), bits),
            bits, channels, 48000, f'pcm_source seed 9639+bits*11+channels; {count} contiguous generated samples')
    count = max(131070, math.ceil(args.seconds * 48000))
    add('maximum-block-32-8', packed(pcm_source(32, 8, count, 'ar'), 32),
        32, 8, 48000, 'deterministic correlated signal; at least two full maximum blocks', block=65535)
    for number in [1, 28, 39, 60]:
        source = next((ROOT / 'validation/cache/flac-test-files/subset').glob(f'{number:02} - *.flac'))
        (channels, bits, rate), pcm = ref.decode(source)
        available = len(pcm) // channels
        count = min(available, math.ceil(args.seconds * rate))
        add(f'recording-{number}', packed(pcm[:count * channels], bits), bits, channels, rate,
            f'original contiguous prefix {count}/{available} samples; no repetition/resampling', source)
    source = ROOT / 'validation/cache/hardening-benchmark/speech.wav'
    if sha(source) != 'c65fcd726d6b08c82c1e5dc7558f863cd8d483e3ed2f4a7bcf271dc1865ada14':
        raise ValueError('cached VOiCES fixture changed')
    with wave.open(str(source), 'rb') as wav:
        assert wav.getsampwidth() == 2
        add('speech-voices', wav.readframes(wav.getnframes()), 16, wav.getnchannels(),
            wav.getframerate(), 'complete cached VOiCES utterance; no repetition/resampling', source)
    save(args.manifest, dict(seconds_requested=args.seconds, cases=cases,
                             generator_sha256=sha(ROOT / 'scripts/validate_encoder.py')))


def measure(command, timeout):
    # Temporary files avoid pipe backpressure on diagnostics while polling RSS.
    import tempfile
    start = time.perf_counter()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err)
        monitored = psutil.Process(proc.pid)
        peak = 0
        while proc.poll() is None:
            try:
                mem = monitored.memory_info()
                peak = max(peak, getattr(mem, 'peak_wset', mem.rss))
            except psutil.NoSuchProcess:
                pass
            if time.perf_counter() - start > timeout:
                proc.kill()
                proc.wait()
                raise TimeoutError(command)
            time.sleep(.002)
        elapsed = time.perf_counter() - start
        out.seek(0)
        err.seek(0)
        stdout, stderr = out.read().decode(errors='replace'), err.read().decode(errors='replace')
        if proc.returncode:
            raise RuntimeError(f'{command}: exit {proc.returncode}\n{stdout}\n{stderr}')
    return dict(wall_seconds=elapsed, peak_process_bytes=peak, stdout=stdout)


def command_for(codec, binary, case, output, core, batch):
    raw = str(ROOT / case['path'])
    if codec == 'libflac':
        return [str(binary), '-8', '-f', '-s', '--lax', '--no-padding', '--no-seektable',
                '--force-raw-format', '--endian=little', '--sign=signed',
                f"--channels={case['channels']}", f"--bps={case['bits']}",
                f"--sample-rate={case['rate']}", f"--blocksize={case['block']}", '-o', str(output), raw]
    if core:
        return [str(binary), raw, str(output), str(case['channels']), str(case['bits']),
                str(case['rate']), str(case['block']), str(batch)]
    return [str(binary), 'encode', raw, str(output), '--raw', '--sample-rate', str(case['rate']),
            '--channels', str(case['channels']), '--bits', str(case['bits']),
            '--block-size', str(case['block']), '--effort', '8']


def timed(codec, binaries, case, output, args, batch):
    command = command_for(codec, binaries[codec], case, output, args.core, batch)
    result = measure(command, args.timeout)
    result['command'] = command
    result['seconds'] = result['wall_seconds']
    result['timing_domain'] = 'process wall seconds including startup and IO'
    if args.core and codec != 'libflac':
        lines = [line.split() for line in result['stdout'].splitlines() if line.startswith('CORE8 ')]
        assert len(lines) == 1 and int(lines[0][1]) == batch, result['stdout']
        result.update(batch=batch, batch_core_seconds=float(lines[0][2]) / 1e6,
                      internal_warmup_seconds=float(lines[0][3]) / 1e6,
                      seconds=float(lines[0][2]) / (1e6 * batch),
                      timing_domain='encode_pcm only; batch mean; comparisons and all IO excluded')
    return result


def validate(output, case, ref, args):
    props, pcm = ref.decode(output)
    assert props == (case['channels'], case['bits'], case['rate']), props
    expected = (ROOT / case['path']).read_bytes()
    assert packed(pcm, case['bits']) == expected, 'libFLAC PCM mismatch'
    subprocess.run([str(args.flac), '-t', '-s', str(output)], check=True, capture_output=True, timeout=args.timeout)
    width = case['bits'] // 8
    fmt = f's{case["bits"]}le'
    decoded = subprocess.run([str(args.ffmpeg), '-v', 'error', '-i', str(output),
                              '-map', '0:a:0', '-c:a', 'pcm_' + fmt, '-f', fmt, 'pipe:1'],
                             check=True, capture_output=True, timeout=args.timeout).stdout
    transport = 'native FLAC'
    extra = {}
    if case['block'] == 65535:
        # Explicit preselected transport for this maximum-frame experiment,
        # not a failure-triggered fallback. Native FFmpeg 9.0.1 drops these
        # valid large frames even when encoded by libFLAC (separate evidence).
        extra['ffmpeg_native'] = dict(bytes=len(decoded), exact_pcm=decoded == expected,
                                      pcm_sha256=hashlib.sha256(decoded).hexdigest())
        wrapped = output.with_suffix('.ffmpeg.oga')
        extra['ffmpeg_packetization'] = wrap_file(output, wrapped, args.flac)
        decoded = subprocess.run([str(args.ffmpeg), '-v', 'error', '-i', str(wrapped),
                                  '-map', '0:a:0', '-c:a', 'pcm_' + fmt, '-f', fmt, 'pipe:1'],
                                 check=True, capture_output=True, timeout=args.timeout).stdout
        transport = 'Ogg carrying unchanged frames; boundaries from official libFLAC analysis'
    assert len(expected) % width == 0 and decoded == expected, 'FFmpeg PCM mismatch'
    # flac -t checks STREAMINFO MD5 and frame CRC, both decoders check full PCM.
    return dict(encoded_sha256=sha(output), encoded_bytes=output.stat().st_size,
                libflac_pcm='exact', ffmpeg_pcm='exact', ffmpeg_transport=transport,
                flac_md5_crc='pass', **extra)


def summary(values):
    med = statistics.median(values)
    return dict(median=med, mad=statistics.median(abs(v - med) for v in values),
                minimum=min(values), maximum=max(values))


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
    cases = [c for c in json.loads(args.manifest.read_text(encoding='utf-8'))['cases'] if args.match in c['name']]
    assert cases, 'no cases selected'
    report = dict(status='running', mode='core' if args.core else 'cli', cases=[],
                  platform=platform.platform(), processor=platform.processor(), logical_cpu=cpu,
                  reference=version(ref), ffmpeg_version=subprocess.check_output([str(args.ffmpeg), '-version'], text=True).splitlines()[0],
                  manifest_sha256=sha(args.manifest), script_sha256=sha(__file__),
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
                    pilot.update(codec=codec, **validate(outputs[codec], case, ref, args))
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
                                  host_cpu_before=load, **validate(outputs[codec], case, ref, args))
                    entry['runs'][codec].append(result)
                    entry['timeline'].append(dict(repetition=repetition, position=position, codec=codec))
                    save(args.report, report)
                assert outputs['baseline'].read_bytes() == outputs['candidate'].read_bytes(), 'bitstream changed'
            entry['bitstream_unchanged_every_round'] = True
            entry['summary'] = {}
            for codec, runs in entry['runs'].items():
                measured = [r for r in runs if not r['warmup']]
                assert len({r['encoded_sha256'] for r in runs}) == 1, 'nondeterministic output'
                stats = summary([r['seconds'] for r in measured])
                entry['summary'][codec] = dict(seconds=stats, encoded_bytes=runs[0]['encoded_bytes'],
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
            save(args.report, report)
            print(case['name'], entry['median_reduction_percent'], entry['paired_difference_summary'], flush=True)
        totals = {k: sum(c['summary'][k]['seconds']['median'] for c in report['cases']) for k in binaries}
        worst = min(report['cases'], key=lambda c: c['median_reduction_percent'])
        report.update(status='pass', fixed_set_sum_medians_seconds=totals,
                      fixed_set_reduction_percent=100 * (totals['baseline'] - totals['candidate']) / totals['baseline'],
                      worst_case=dict(name=worst['name'], median_reduction_percent=worst['median_reduction_percent']))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(args.report, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--seconds', type=float, default=10)
    run_parser = commands.add_parser('run')
    for command in [prepare_parser, run_parser]:
        command.add_argument('--manifest', type=Path, default=MANIFEST)
        command.add_argument('--libflac')
    run_parser.add_argument('--baseline', type=Path, required=True)
    run_parser.add_argument('--candidate', type=Path, required=True)
    run_parser.add_argument('--baseline-identity', type=Path, required=True)
    run_parser.add_argument('--candidate-identity', type=Path, required=True)
    run_parser.add_argument('--report', type=Path, required=True)
    run_parser.add_argument('--flac', type=Path, default=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    run_parser.add_argument('--ffmpeg', type=Path, default=Path(shutil.which('ffmpeg') or 'ffmpeg'))
    run_parser.add_argument('--core', action='store_true')
    run_parser.add_argument('--rounds', type=int, default=6)
    run_parser.add_argument('--min-core-seconds', type=float, default=.5)
    run_parser.add_argument('--max-batch', type=int, default=256)
    run_parser.add_argument('--timeout', type=float, default=1800)
    run_parser.add_argument('--match', default='')
    run_parser.add_argument('--cpu', type=int)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else run)(args)


if __name__ == '__main__':
    main()
