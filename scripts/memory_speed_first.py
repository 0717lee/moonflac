"""Scoped speed-first memory gates; run outside controlled timing campaigns.

Compare increasing durations with the largest power-of-two partition tree and
maximum legal block. These probes do not replace historical hour/RF64 stress.
Bitstreams may differ: each output must independently reproduce the original PCM.
"""
import argparse
import json
import os
from pathlib import Path
import platform

from stress_encoder import digest, independent, run, source_hash, version, write_rf64

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--label', default='initial', help='Unique cache label; initial preserves the original path')
    args = p.parse_args()
    if args.report.exists():
        p.error('Preserve existing evidence; choose a new report path')
    if not args.label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.label):
        p.error('label must contain only lowercase letters, digits and hyphens')
    suffix = '' if args.label == 'initial' else '-'+args.label
    work = ROOT/('validation/cache/speed-first-memory'+suffix)
    work.mkdir(parents=True, exist_ok=True)
    args.flac = str(ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    args.timeout = 1800
    binaries = {k: str(v.resolve()) for k, v in [('baseline', args.baseline), ('candidate', args.candidate)]}
    report = dict(status='running', method=__doc__, os=platform.platform(), label=args.label,
                  script_sha256=digest(Path(__file__)), helper_sha256=digest(ROOT/'scripts/stress_encoder.py'),
                  flac=version([args.flac, '--version']), moon=version(['moon', 'version']),
                  current_source_sha256=source_hash(), results=[],
                  binaries={k: dict(path=v, sha256=digest(Path(v))) for k, v in binaries.items()},
                  codec_files={name: digest(ROOT/name) for name in
                               ['encoder_frame.mbt', 'encoder_search.mbt', 'encoder.mbt', 'encoder_lpc.mbt', 'md5.mbt']},
                  gate='For each binary/format, longer duration may increase peak working set by at most 8 MiB. '
                       'Both are frame-bounded workloads; this allowance covers allocator/startup variance. '
                       'Timings include process/I/O and are not controlled benchmark evidence.')

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(args.report.suffix+'.tmp')
        temporary.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        os.replace(temporary, args.report)

    save()
    try:
        for block, channels, bits, durations in [(32768, 2, 16, [2, 20]), (65535, 8, 32, [5, 60])]:
            group = []
            for duration in durations:
                name = f'{duration}s-{channels}ch-{bits}bit-b{block}'
                source = work/(name+'.rf64')
                entry = dict(name=name, block=block, channels=channels, bits=bits, seconds=duration,
                             source=write_rf64(source, duration*48000, 48000, channels, bits), encodes={})
                for codec, binary in binaries.items():
                    assert digest(Path(binary)) == report['binaries'][codec]['sha256'], 'binary changed during run'
                    out = work/(name+'-'+codec+'.flac')
                    result = run([binary, 'encode', str(source), str(out), '--effort', '8', '--block-size', str(block)], 1800)
                    checks = independent(args, out, entry['source']['pcm_md5'], entry['source']['pcm_bytes'])
                    result.update(independent=checks, encoded_sha256=digest(out), encoded_bytes=out.stat().st_size)
                    entry['encodes'][codec] = result
                entry['baseline_bytes_equal'] = (entry['encodes']['baseline']['encoded_sha256'] ==
                                                 entry['encodes']['candidate']['encoded_sha256'])
                report['results'].append(entry)
                group.append(entry)
                save()
                print(name, {k:v['os_peak_working_set_bytes'] for k,v in entry['encodes'].items()}, flush=True)
            for codec in binaries:
                growth = (group[1]['encodes'][codec]['os_peak_working_set_bytes'] -
                          group[0]['encodes'][codec]['os_peak_working_set_bytes'])
                report.setdefault('duration_memory_gates', []).append(dict(
                    codec=codec, channels=channels, bits=bits, block=block,
                    durations=durations, peak_growth_bytes=growth, limit_bytes=8*1024**2))
                assert growth <= 8*1024**2, ('duration memory growth', codec, growth)
        for codec, binary in binaries.items():
            assert digest(Path(binary)) == report['binaries'][codec]['sha256'], 'binary changed during run'
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
