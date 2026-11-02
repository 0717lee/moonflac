#!/usr/bin/env python3
"""Bounded-memory RF64/hour stress and seeded, non-coverage-guided differential fuzz.

long defaults physically write a >4 GiB PCM RF64, then independently decode it.
Small --durations values are smoke checks, not evidence of the default gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import struct
import subprocess
import tempfile
import threading
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
PROCESS_RSS_LIMIT = 512 * 1024**2


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def source_hash():
    h = hashlib.sha256()
    sources = []
    for directory, children, files in os.walk(ROOT):
        # Do not stat/traverse foreign-platform build artifacts (e.g. WSL symlinks).
        children[:] = [name for name in children if name not in ('_build', '.mooncakes', 'cache')]
        sources.extend(Path(directory)/name for name in files if Path(name).suffix in ('.mbt', '.c'))
    for p in sorted(sources):
        h.update(p.relative_to(ROOT).as_posix().encode() + b'\0')
        h.update(p.read_bytes())
    return h.hexdigest()


def run(command, timeout, raw_stdout=False, allow_error=False):
    """Drain output concurrently; timeout includes pipe draining and child lifetime."""
    started = time.perf_counter()
    h = hashlib.md5()
    count = 0
    failure = []
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as out:
        child = subprocess.Popen(command, stdout=subprocess.PIPE if raw_stdout else out, stderr=err)
        proc = psutil.Process(child.pid)

        def drain():
            nonlocal count
            try:
                for part in iter(lambda: child.stdout.read(1048576), b''):
                    h.update(part)
                    count += len(part)
            except Exception as exc:
                failure.append(repr(exc))

        reader = threading.Thread(target=drain, daemon=True) if raw_stdout else None
        if reader:
            reader.start()
        peak = os_peak = polls = 0
        try:
            while child.poll() is None:
                if time.perf_counter() - started > timeout:
                    raise TimeoutError(f'timeout after {timeout}s: {command}')
                try:
                    m = proc.memory_info()
                    peak = max(peak, m.rss)
                    os_peak = max(os_peak, getattr(m, 'peak_wset', m.rss))
                    polls += 1
                    if m.rss > PROCESS_RSS_LIMIT:
                        raise RuntimeError(f'process RSS exceeded {PROCESS_RSS_LIMIT} bytes: {command}')
                except psutil.NoSuchProcess:
                    pass
                time.sleep(.005)
        except BaseException:
            child.kill()
            child.wait()
            raise
        finally:
            if reader:
                reader.join(10)
        if reader and reader.is_alive():
            raise RuntimeError('stdout reader did not terminate')
        if failure:
            raise RuntimeError(failure)
        err.seek(0)
        diagnostic = err.read(16384).decode(errors='replace')
        if child.returncode and not allow_error:
            raise RuntimeError((command, child.returncode, diagnostic))
        return dict(command=command, returncode=child.returncode, seconds=time.perf_counter()-started,
                    sampled_peak_rss_bytes=peak, os_peak_working_set_bytes=os_peak, memory_polls=polls,
                    stdout_pcm_bytes=count if raw_stdout else None,
                    stdout_pcm_md5=h.hexdigest() if raw_stdout else None, stderr=diagnostic)


def version(command):
    p = subprocess.run(command, capture_output=True, check=True, timeout=30)
    return (p.stdout + p.stderr).decode(errors='replace').splitlines()[0]


def rf64_header(frames, rate, channels, bits):
    size = frames * channels * (bits // 8)
    mask = {2: 3, 8: 0x63f}[channels]
    fmt = struct.pack('<HHIIHHHHI', 0xfffe, channels, rate, rate*channels*(bits//8),
                      channels*(bits//8), bits, 22, bits, mask)
    fmt += bytes.fromhex('0100000000001000800000aa00389b71')
    # Header is 104 bytes; ds64 RIFF length excludes its first eight bytes.
    return (b'RF64\xff\xff\xff\xffWAVEds64' + struct.pack('<IQQQI', 28, size+96, size, frames, 0)
            + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data\xff\xff\xff\xff')


def write_rf64(path, frames, rate, channels, bits):
    """Write every PCM byte (no truncate, seeks, sparse or compression attribute)."""
    width = bits // 8
    period = bytearray()
    for i in range(512):
        for c in range(channels):
            phase = (i + c*19) % 512
            value = (phase if phase < 256 else 511-phase) - 128
            value *= 1 << (bits-10)
            period.extend(value.to_bytes(width, 'little', signed=True))
    chunk = bytes(period)*128
    remaining = frames*channels*width
    h = hashlib.md5()
    started = time.perf_counter()
    with path.open('wb') as f:
        header = rf64_header(frames, rate, channels, bits)
        assert len(header) == 104
        f.write(header)
        while remaining:
            part = chunk[:min(remaining, len(chunk))]
            f.write(part)
            h.update(part)
            remaining -= len(part)
        f.flush()
        os.fsync(f.fileno())
    size = frames*channels*width
    assert path.stat().st_size == size+104
    with path.open('rb') as f:
        actual = f.read(104)
    assert actual == header and struct.unpack_from('<QQQ', actual, 20) == (size+96, size, frames)
    return dict(pcm_bytes=size, pcm_md5=h.hexdigest(), generation_seconds=time.perf_counter()-started,
                physically_written_bytes=size+104, rf64_ds64_verified=True)


def independent(args, encoded, expected_md5, expected_bytes):
    timeout = args.case_timeout if getattr(args, 'action', None) == 'fuzz' else args.timeout
    test = run([args.flac, '--silent', '-t', str(encoded)], timeout)
    decoded = run([args.flac, '--silent', '-d', '-c', '--force-raw-format', '--endian=little',
                   '--sign=signed', str(encoded)], timeout, raw_stdout=True)
    assert decoded['stdout_pcm_bytes'] == expected_bytes, decoded
    assert decoded['stdout_pcm_md5'] == expected_md5, decoded
    with encoded.open('rb') as f:
        header = f.read(42)
    assert header[:4] == b'fLaC' and header[26:42].hex() == expected_md5
    return dict(flac_test=test, libflac_decode=decoded)


def save(args, report):
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix+'.tmp')
    temporary.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    os.replace(temporary, args.report)


def long(args, report):
    for channels, bits, effort, block in ((2, 24, 5, 4096), (8, 32, 8, 65535)):
        for duration in args.durations:
            frames = duration*48000
            required = frames*channels*(bits//8)+104
            if shutil.disk_usage(args.directory).free < required + 512*1024**2:
                raise RuntimeError(f'Need {required+512*1024**2} free bytes for physical RF64 input')
            name = f'{duration}s-{channels}ch-{bits}bit-e{effort}-b{block}'
            source, encoded = args.directory/(name+'.rf64'), args.directory/(name+'.flac')
            original = write_rf64(source, frames, 48000, channels, bits)
            encoded_run = run([args.cli, 'encode', str(source), str(encoded), '--effort', str(effort),
                               '--block-size', str(block)], args.timeout)
            checks = independent(args, encoded, original['pcm_md5'], original['pcm_bytes'])
            result = dict(name=name, duration_seconds=duration, sample_frames=frames, rate=48000,
                          channels=channels, bits=bits, effort=effort, block_size=block,
                          source=original, encode=encoded_run, independent=checks,
                          encoded_bytes=encoded.stat().st_size,
                          realtime_multiple=duration/encoded_run['seconds'])
            report['results'].append(result)
            save(args, report)
            print(json.dumps(result), flush=True)
            if not args.keep_inputs:
                source.unlink()
    report['hour_gate_passed'] = all(any(x['duration_seconds'] >= 3600 and x['channels'] == c
                                       for x in report['results']) for c in (2, 8))
    report['physical_gt_4gib_gate_passed'] = any(x['source']['pcm_bytes'] > 2**32 for x in report['results'])


def fuzz(args, report):
    rng = random.Random(args.seed)
    started = time.monotonic()
    counts = dict(encoded=0, mutations=0, mutually_accepted=0, moon_rejected=0, reference_rejected=0,
                  moon_only_accepted=0, reference_only_accepted=0)
    iteration = 0
    while time.monotonic()-started < args.seconds or iteration < args.min_cases:
        bits, channels = rng.choice([8, 16, 24, 32]), rng.randrange(1, 9)
        frames = rng.choice([1, 16, 31, 257, 1024, 4097])
        width = bits//8
        lo, hi = -(1 << (bits-1)), (1 << (bits-1))-1
        values = [rng.randint(lo, hi) if i % 7 else rng.choice([lo, hi, 0, -1, 1])
                  for i in range(frames*channels)]
        raw = b''.join(v.to_bytes(width, 'little', signed=True) for v in values)
        source, encoded = args.directory/'fuzz.raw', args.directory/'fuzz.flac'
        source.write_bytes(raw)
        effort, block = rng.randrange(9), rng.choice([16, 192, 256, 1024, 4096, 65535])
        report['current_case'] = dict(iteration=iteration, bits=bits, channels=channels, frames=frames,
                                      effort=effort, block_size=block, pcm_sha256=hashlib.sha256(raw).hexdigest())
        save(args, report)
        command = [args.cli, 'encode', str(source), str(encoded), '--raw', '--sample-rate', '48000',
                   '--channels', str(channels), '--bits', str(bits), '--effort', str(effort),
                   '--block-size', str(block)]
        run(command, args.case_timeout)
        independent(args, encoded, hashlib.md5(raw).hexdigest(), len(raw))
        counts['encoded'] += 1
        data = encoded.read_bytes()
        for kind in ('bit', 'truncate', 'insert', 'delete'):
            payload = bytearray(data)
            at = rng.randrange(len(payload))
            if kind == 'bit': payload[at] ^= 1 << rng.randrange(8)
            elif kind == 'truncate': del payload[at:]
            elif kind == 'insert': payload[at:at] = rng.randbytes(rng.randrange(1, 17))
            else: del payload[at:at+rng.randrange(1, 17)]
            mutation, output = args.directory/'mutation.flac', args.directory/'mutation.raw'
            mutation.write_bytes(payload)
            report['current_mutation'] = dict(kind=kind, offset=at, sha256=hashlib.sha256(payload).hexdigest())
            m = run([args.cli, 'decode', str(mutation), str(output), '--raw'], args.case_timeout, allow_error=True)
            # Documented decode failures are 2 (usage), 3 (format), 4 (I/O).
            if m['returncode'] not in (0, 2, 3, 4):
                raise RuntimeError(('unexpected CLI termination', iteration, kind, m))
            r = run([args.flac, '--silent', '-d', '-c', '--force-raw-format', '--endian=little',
                     '--sign=signed', str(mutation)], args.case_timeout, raw_stdout=True, allow_error=True)
            if r['returncode'] not in (0, 1):
                raise RuntimeError(('unexpected reference termination', iteration, kind, r))
            counts['mutations'] += 1
            counts['moon_rejected'] += int(m['returncode'] != 0)
            counts['reference_rejected'] += int(r['returncode'] != 0)
            counts['moon_only_accepted'] += int(m['returncode'] == 0 and r['returncode'] != 0)
            counts['reference_only_accepted'] += int(r['returncode'] == 0 and m['returncode'] != 0)
            if (m['returncode'] == 0) != (r['returncode'] == 0):
                reproducer = args.directory/'disagreements'/f'{iteration:06}-{kind}'
                reproducer.mkdir(parents=True, exist_ok=True)
                (reproducer/'mutated.flac').write_bytes(payload)
                (reproducer/'original.flac').write_bytes(data)
                entry = dict(seed=args.seed, case=report['current_case'].copy(),
                             mutation=report['current_mutation'].copy(), moon=m, reference=r,
                             directory=str(reproducer.resolve()))
                (reproducer/'diagnostics.json').write_text(json.dumps(entry, indent=2)+'\n', encoding='utf-8')
                with (args.directory/'disagreements.jsonl').open('a', encoding='utf-8') as journal:
                    journal.write(json.dumps(entry)+'\n')
                    journal.flush()
                    os.fsync(journal.fileno())
                report.setdefault('disagreements', []).append(entry)
                save(args, report)
            if m['returncode'] == r['returncode'] == 0:
                actual = output.read_bytes()
                assert len(actual) == r['stdout_pcm_bytes'] and hashlib.md5(actual).hexdigest() == r['stdout_pcm_md5'], (iteration, kind)
                counts['mutually_accepted'] += 1
        iteration += 1
        report.update(counts=counts, elapsed_seconds=time.monotonic()-started, last_iteration=iteration)
        save(args, report)
        if iteration % 25 == 0:
            print(json.dumps(report['counts']), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['long', 'fuzz'])
    p.add_argument('--cli', required=True)
    p.add_argument('--flac', required=True)
    p.add_argument('--directory', type=Path, default=ROOT/'validation/cache/encoder-stress')
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--durations', type=int, nargs='+', default=[60, 3600])
    p.add_argument('--timeout', type=float, default=28800)
    p.add_argument('--keep-inputs', action='store_true')
    p.add_argument('--seed', type=int, default=963920260929)
    p.add_argument('--seconds', type=float, default=1800)
    p.add_argument('--min-cases', type=int, default=100)
    p.add_argument('--case-timeout', type=float, default=60)
    args = p.parse_args()
    if any(n <= 0 for n in args.durations) or args.timeout <= 0 or args.case_timeout <= 0 or args.seconds < 0 or args.min_cases < 0:
        p.error('durations and timeouts must be positive; fuzz limits must be nonnegative')
    args.cli, args.flac = str(Path(args.cli).resolve()), str(Path(args.flac).resolve())
    args.directory.mkdir(parents=True, exist_ok=True)
    report = dict(action=args.action, status='running', source_sha256=source_hash(), cli_sha256=digest(Path(args.cli)),
                  os=platform.platform(), python=platform.python_version(), psutil=psutil.__version__,
                  flac=version([args.flac, '--version']), moon=version(['moon', 'version']),
                  process_rss_limit_bytes=PROCESS_RSS_LIMIT,
                  seed=args.seed, arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                  method='Wall time includes process and I/O; memory sampled every 5ms; Windows peak_wset when available. '
                         'Seeded non-coverage-guided fuzz, not coverage-guided. Differential PCM comparison requires both decoders to accept; '
                         'accept/reject disagreements counted, not equated to codec defects. Long source: periodic channel-shifted triangle integer PCM.',
                  results=[])
    save(args, report)
    try:
        (long if args.action == 'long' else fuzz)(args, report)
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', failure=repr(exc))
        save(args, report)
        raise
    save(args, report)


if __name__ == '__main__':
    main()
