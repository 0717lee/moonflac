"""Independent fixed-manifest CLI/core quality checks, without timing claims."""
import argparse
import json
import subprocess
from pathlib import Path

from benchmark_effort8 import ROOT, LibFLAC, command_for, library, sha
from benchmark_faster_than_libflac import artifact_identity, load, source_identity
from benchmark_speed_first import size_check, validate_sized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--group', choices=['original-cli', 'original-core', 'long'], required=True)
    parser.add_argument('--cli-identity', type=Path, required=True)
    parser.add_argument('--core-identity', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--references', type=Path,
                        default=ROOT / 'validation/evidence/faster-than-libflac-inputs-references.json')
    parser.add_argument('--flac', type=Path,
                        default=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    assert not args.report.exists() and not args.work.exists(), 'Preserve prior evidence'
    args.smoke_case = None
    cases, _ = load(args)
    identities = {'cli': args.cli_identity, 'core': args.core_identity}
    bindings, binaries = {}, {}
    for role, path in identities.items():
        identity = json.loads(path.read_text())
        binary = ROOT / identity[role]['path']
        bindings[role] = dict(artifact=artifact_identity(path, binary, role),
                              sources=source_identity(path))
        binaries[role] = binary
    args.work.mkdir(parents=True)
    ref = LibFLAC(library(None))
    report = dict(status='running', scope=__doc__, acceptance_eligible=False,
                  manifest=dict(path=str(args.manifest), sha256=sha(args.manifest)),
                  references_sha256=sha(args.references), bindings=bindings,
                  script_sha256=sha(Path(__file__)), cases=[])

    def save():
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')

    try:
        for case in cases:
            row = dict(name=case['name'], pcm_sha256=case['pcm_sha256'], outputs={})
            report['cases'].append(row)
            args.large_frame_transport = case['block'] in (32768, 65535)
            for role, binary in binaries.items():
                output = (args.work / (case['name'] + '-' + role + '.flac')).resolve()
                command = command_for('candidate', binary, case, output, False, 1) if role == 'cli' else [
                    str(binary), str(ROOT / case['path']), str(output), str(case['channels']),
                    str(case['bits']), str(case['rate']), str(case['block']), '1', '8']
                process = subprocess.run(command, capture_output=True, timeout=args.timeout)
                if process.returncode:
                    raise RuntimeError((case['name'], role, process.returncode,
                                        process.stderr.decode('utf8', errors='replace')))
                checked = validate_sized(output, case, ref, args)
                row['outputs'][role] = dict(command=command, verification=checked,
                    size_budget=size_check(case['quality_anchor']['encoded_bytes'],
                                           checked['encoded_bytes'], 1.03))
                save()
            row['cli_core_byte_identity'] = (
                row['outputs']['cli']['verification']['encoded_sha256'] ==
                row['outputs']['core']['verification']['encoded_sha256'])
            assert row['cli_core_byte_identity'], case['name']
            print(case['name'], 'PCM/CRC/MD5 and CLI/core bytes pass', flush=True)
        report['aggregate'] = {role: size_check(
            sum(c['quality_anchor']['encoded_bytes'] for c in cases),
            sum(r['outputs'][role]['verification']['encoded_bytes'] for r in report['cases']),
            1.01) for role in binaries}
        for role, path in identities.items():
            assert bindings[role]['artifact'] == artifact_identity(path, binaries[role], role)
            assert bindings[role]['sources'] == source_identity(path)
        report['status'] = 'pass' if all(v['passed'] for v in report['aggregate'].values()) and all(
            output['size_budget']['passed'] for row in report['cases']
            for output in row['outputs'].values()) else 'quality-fail'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save()
    if report['status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
