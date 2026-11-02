"""Compare per-frame scratch bounds over increasing stream durations.

Run separately from controlled performance benchmarks. This targets the changed
scratch lifetime, including the largest power-of-two partition tree and maximum
legal block size; it does not repeat or replace the accepted hour/RF64 campaign.
"""
import argparse
import json
from pathlib import Path

from stress_encoder import digest, run, write_rf64
from benchmark_faster_than_libflac import artifact_identity, source_identity

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--baseline-identity', type=Path)
    p.add_argument('--candidate-identity', type=Path)
    p.add_argument('--work-dir', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    assert not args.report.exists(), 'Preserve existing evidence'
    if bool(args.baseline_identity) != bool(args.candidate_identity):
        p.error('provide both artifact identities together')
    work = args.work_dir or ROOT / 'validation/cache/effort8-memory'
    work.mkdir(parents=True, exist_ok=args.work_dir is None)
    flac = ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
    binaries = {k: str(v.resolve()) for k, v in [('baseline', args.baseline), ('candidate', args.candidate)]}
    report = dict(status='running', method=__doc__, results=[],
                  binaries={k: dict(path=v, sha256=digest(Path(v))) for k, v in binaries.items()},
                  workspace_encoder_frame_sha256=digest(ROOT / 'encoder_frame.mbt'),
                  workspace_source_note='Workspace hash is contextual; explicit identities below bind the tested executables.',
                  script_sha256=digest(Path(__file__)),
                  independent_flac=dict(path=str(flac), sha256=digest(flac)))
    identities = {'baseline': args.baseline_identity, 'candidate': args.candidate_identity}
    if args.baseline_identity:
        report['bindings'] = {role: dict(artifact=artifact_identity(path, Path(binaries[role]), 'cli'),
                                        sources=source_identity(path)) for role, path in identities.items()}

    def save():
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    try:
        for block, channels, bits, durations in [(32768, 2, 16, [2, 20]), (65535, 8, 32, [5, 60])]:
            for duration in durations:
                name = f'{duration}s-{channels}ch-{bits}bit-b{block}'
                source = work / (name+'.rf64')
                entry = dict(name=name, block=block, channels=channels, bits=bits, seconds=duration,
                             source=write_rf64(source, duration*48000, 48000, channels, bits), encodes={})
                outputs = []
                for codec, binary in binaries.items():
                    out = work / (name+'-'+codec+'.flac')
                    result = run([binary, 'encode', str(source), str(out), '--effort', '8', '--block-size', str(block)], 1800)
                    verified = run([str(flac), '-t', '-s', str(out)], 60)
                    pcm = run([str(flac), '-d', '-s', '-c', '--force-raw-format', '--endian=little', '--sign=signed', str(out)], 120, raw_stdout=True)
                    assert pcm['stdout_pcm_bytes'] == entry['source']['pcm_bytes']
                    assert pcm['stdout_pcm_md5'] == entry['source']['pcm_md5']
                    result.update(libflac_pcm=pcm, integrity=verified, encoded_sha256=digest(out), encoded_bytes=out.stat().st_size)
                    entry['encodes'][codec] = result
                    outputs.append(out)
                assert outputs[0].read_bytes() == outputs[1].read_bytes()
                entry['baseline_bytes_equal'] = True
                report['results'].append(entry)
                save()
                print(name, {k:v['os_peak_working_set_bytes'] for k,v in entry['encodes'].items()}, flush=True)
        if args.baseline_identity:
            for role, path in identities.items():
                assert report['bindings'][role]['artifact'] == artifact_identity(path, Path(binaries[role]), 'cli')
                assert report['bindings'][role]['sources'] == source_identity(path)
        assert report['independent_flac']['sha256'] == digest(flac)
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
