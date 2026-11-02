"""Revision4 affected short-block memory probe; no repeat of prior long/max-block evidence."""
import argparse
import json
import os
from pathlib import Path
import platform

from stress_encoder import digest, independent, run, version, write_rf64

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if args.report.exists():
        p.error('preserve existing evidence')
    work = ROOT/'validation/cache/speed-first-memory-revision4'
    work.mkdir(parents=True, exist_ok=True)
    args.flac = str(ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    args.timeout = 1800
    binary = args.candidate.resolve()
    identity = json.loads(args.identity.read_text(encoding='utf-8'))

    def current_identity():
        return dict(cli_sha256=digest(binary), sources={name: digest(ROOT/name) for name in identity['sources']})

    before = current_identity()
    assert before['cli_sha256'] == identity['cli']['sha256']
    assert before['sources'] == identity['sources']
    report = dict(status='running', method=__doc__, os=platform.platform(), label='revision4-short-block',
                  script_sha256=digest(Path(__file__)), helper_sha256=digest(ROOT/'scripts/stress_encoder.py'),
                  frozen_identity=dict(path=str(args.identity), sha256=digest(args.identity)), identity_before=before,
                  binaries=dict(candidate=dict(path=str(binary), sha256=before['cli_sha256'])),
                  flac=version([args.flac, '--version']), moon=version(['moon', 'version']), results=[],
                  gate='Candidate-only restored full LPC pool at actual block <=256. '
                       '2 to 20 seconds peak growth <=8 MiB per format; independent original PCM/CRC/MD5. '
                       'Wall times include I/O/process under concurrent correctness workload; not controlled performance evidence.')

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(args.report.suffix+'.tmp')
        temporary.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        os.replace(temporary, args.report)

    save()
    try:
        for channels, bits in [(2, 16), (8, 32)]:
            group = []
            for duration in (2, 20):
                name = f'{duration}s-{channels}ch-{bits}bit-b256'
                source, out = work/(name+'.rf64'), work/(name+'.flac')
                original = write_rf64(source, duration*48000, 48000, channels, bits)
                result = run([str(binary), 'encode', str(source), str(out), '--effort', '8', '--block-size', '256'], 1800)
                result.update(independent=independent(args, out, original['pcm_md5'], original['pcm_bytes']),
                              encoded_sha256=digest(out), encoded_bytes=out.stat().st_size)
                entry = dict(name=name, block=256, channels=channels, bits=bits, seconds=duration,
                             source=original, encodes=dict(candidate=result))
                group.append(entry)
                report['results'].append(entry)
                save()
                print(name, result['os_peak_working_set_bytes'], flush=True)
            growth = group[1]['encodes']['candidate']['os_peak_working_set_bytes']-group[0]['encodes']['candidate']['os_peak_working_set_bytes']
            report.setdefault('duration_memory_gates', []).append(dict(codec='candidate', channels=channels, bits=bits,
                block=256, durations=[2, 20], peak_growth_bytes=growth, limit_bytes=8*1024**2))
            assert growth <= 8*1024**2, ('duration memory growth', channels, growth)
        report['identity_after'] = current_identity()
        assert report['identity_after'] == before, 'codec identity changed during probe'
        report['status'] = 'pass'
    except BaseException as exc:
        report.update(status='fail', error=repr(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
