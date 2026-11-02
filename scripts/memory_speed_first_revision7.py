"""Revision7 widths-array and full-LPC lifetime probes; not controlled timing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import struct

from stress_encoder import digest, run, version
from validate import LibFLAC, library
from validate_encoder import reference_frames

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CLI = '71be364ccf233d29d5a3327ddd78ba7ad076bdb4c6fcc34b11a00d0a482041a9'


def source(path, frames, channels, bits, kind):
    rng = random.Random(963907)
    period = 565 if kind == 'sparse25' else 65536
    samples = []
    for i in range(period):
        for c in range(channels):
            if kind == 'dense16':
                value = rng.randrange(-32768, 32768)
            elif kind == 'sparse25':
                value = (2, 1, -1, -2, 1)[(i+c) % 5]
                if (i+c*13) % 113 == 0:
                    value = ((1 << 24)-1) * (-1 if c % 2 else 1)
            else:
                phase = (i+c*19) % 512
                value = ((phase if phase < 256 else 511-phase)-128) * (1 << 22)
            samples.append(value)
    block = struct.pack('<'+('h' if bits == 16 else 'i')*len(samples), *samples)
    width = (bits+7)//8
    left = frames*channels*width
    md5 = hashlib.md5()
    with path.open('wb') as f:
        while left:
            chunk = block[:min(left, len(block))]
            f.write(chunk)
            md5.update(chunk)
            left -= len(chunk)
    return dict(pcm_bytes=frames*channels*width, pcm_md5=md5.hexdigest(), pattern=kind,
                pattern_period_frames=period, seed=963907)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if args.report.exists():
        p.error('preserve existing report')
    identity = json.loads(args.identity.read_text(encoding='utf-8'))
    binary = args.candidate.resolve()
    flac = ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
    ref = LibFLAC(library(None))
    work = ROOT/'validation/cache/speed-first-memory-revision7'
    work.mkdir(parents=True, exist_ok=True)

    def state():
        return dict(cli_sha256=digest(binary), sources={n: digest(ROOT/n) for n in identity['sources']})

    before = state()
    assert before['cli_sha256'] == EXPECTED_CLI == identity['cli']['sha256']
    assert before['sources'] == identity['sources']
    report = dict(status='running', method=__doc__, os=platform.platform(), results=[],
                  script_sha256=digest(Path(__file__)), identity_before=before,
                  frozen_identity=dict(path=str(args.identity), sha256=digest(args.identity)),
                  binaries=dict(candidate=dict(path=str(binary), sha256=EXPECTED_CLI)),
                  flac=version([str(flac), '--version']), moon=version(['moon', 'version']),
                  gate='Each 2 to 20 second peak growth <=8 MiB. RSS is 5ms sampled / Windows peak_wset. '
                       'libFLAC frame callbacks hash original signed integer PCM, including right-aligned 25-bit PCM; '
                       'flac-t verifies CRC/MD5 independently. Times are concurrent correctness observations only.')

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temp = args.report.with_suffix('.json.tmp')
        temp.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        os.replace(temp, args.report)

    save()
    try:
        for block, channels, bits, kind in [(32768, 2, 16, 'dense16'), (32768, 8, 25, 'sparse25'), (65535, 8, 32, 'triangle32')]:
            group = []
            for duration in (2, 20):
                name = f'{kind}-{duration}s-{channels}ch-{bits}bit-b{block}'
                raw, out = work/(name+'.raw'), work/(name+'.flac')
                original = source(raw, duration*48000, channels, bits, kind)
                result = run([str(binary), 'encode', str(raw), str(out), '--raw', '--sample-rate', '48000',
                              '--channels', str(channels), '--bits', str(bits), '--effort', '8', '--block-size', str(block)], 1800)
                integrity = run([str(flac), '-t', '-s', str(out)], 120)
                md5, size = hashlib.md5(), 0

                def consume(fmt, count, pcm):
                    nonlocal size
                    assert fmt == (channels, bits, 48000)
                    md5.update(pcm)
                    size += len(pcm)

                reference_frames(ref, out, consume)
                assert size == original['pcm_bytes'] and md5.hexdigest() == original['pcm_md5']
                with out.open('rb') as f:
                    header = f.read(42)
                assert header[:4] == b'fLaC' and header[26:42].hex() == original['pcm_md5']
                result.update(independent=dict(flac_test=integrity, pcm_bytes=size, pcm_md5=md5.hexdigest(),
                                              streaminfo_md5=header[26:42].hex()),
                              encoded_bytes=out.stat().st_size, encoded_sha256=digest(out))
                entry = dict(name=name, block=block, channels=channels, bits=bits, seconds=duration,
                             source=original, encodes=dict(candidate=result))
                group.append(entry)
                report['results'].append(entry)
                save()
                print(name, result['os_peak_working_set_bytes'], flush=True)
            growth = group[1]['encodes']['candidate']['os_peak_working_set_bytes']-group[0]['encodes']['candidate']['os_peak_working_set_bytes']
            report.setdefault('duration_memory_gates', []).append(dict(codec='candidate', block=block, channels=channels,
                bits=bits, pattern=kind, durations=[2, 20], peak_growth_bytes=growth, limit_bytes=8*1024**2))
            assert growth <= 8*1024**2
        report['identity_after'] = state()
        assert report['identity_after'] == before
        report['status'] = 'pass'
    except BaseException as exc:
        report.update(status='fail', error=repr(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
