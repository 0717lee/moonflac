"""32 sealed pulse fixtures on JS/wasm-gc versus verified native revision7.

Run only after controlled timing has ended:
  python scripts/validate_speed_first_pulses_cross.py

Existing validation/encoder binaries contain fixed embedded fixtures and expose
no arbitrary PCM/config input. This runner uses the same generated encode_pcm
and hexadecimal-output pattern in an isolated source module. It builds only the
two required targets and never edits production or the existing generated package.
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from validate_encoder import LibFLAC, library, version
from validate_speed_first_pulses import validate, sha

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT / '_build/speed-first/pulses-cross-revision7'


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def source_module(destination, identity, cases):
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, expected in identity['sources'].items():
        source = ROOT / name
        assert sha(source) == expected, 'frozen source changed: ' + name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[name] = expected
    for name in ['moon.mod', 'moon.pkg', 'README.md', 'LICENSE']:
        source = ROOT / name
        shutil.copy2(source, destination / name)
        files[name] = sha(source)
    shutil.copytree(ROOT / '.mooncakes', destination / '.mooncakes')
    package = destination / 'validation/pulses'
    package.mkdir(parents=True)
    # Same representation and native MoonBit public API as validate_encoder.py.
    text = '''// Generated from the sealed pulse manifest; external libFLAC checks every byte stream.
///|
fn dump(name : String, data : Bytes) -> Unit {
  let hex = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]
  let output = StringBuilder()
  for byte in data {
    output.write_string(hex[byte.to_int() >> 4])
    output.write_string(hex[byte.to_int() & 15])
  }
  println("ENCODED " + name + " " + output.to_string())
}
///|
fn run() -> Unit raise {
'''
    for index, case in enumerate(cases):
        raw = (ROOT / case['path']).read_bytes()
        assert sha(ROOT / case['path']) == case['pcm_sha256']
        width = (case['bits'] + 7) // 8
        values = [int.from_bytes(raw[i:i + width], 'little', signed=True)
                  for i in range(0, len(raw), width)]
        assert len(values) == case['samples'] * case['channels']
        assert re.fullmatch(r'[a-zA-Z0-9_-]+', case['name']), 'fixture name must be safe MoonBit literal'
        text += f'  let pcm{index} : Array[Int] = [\n'
        for at in range(0, len(values), 16):
            text += '    ' + ', '.join(str(value) for value in values[at:at + 16]) + ',\n'
        text += '  ]\n'
        text += f'''  let config{index} = @flac.EncoderConfig::new(
    {{ sample_rate: {case['rate']}, channels: {case['channels']}, bits_per_sample: {case['bits']} }},
    block_size={case['block']}, effort={case['effort']}, variable_block={str(case['variable']).lower()},
  )
  dump("{case['name']}", @flac.encode_pcm(pcm{index}, config{index}))
'''
    text += '''}
///|
fn main {
  run() catch {
    error => {
      println("ERROR \\{error}")
      panic()
    }
  }
}
'''
    (package / 'main.mbt').write_text(text, encoding='utf-8')
    (package / 'moon.pkg').write_text('import { "0717lee/moonflac" @flac }\npkgtype(kind: "executable")\n', encoding='utf-8')
    files['validation/pulses/main.mbt'] = sha(package / 'main.mbt')
    files['validation/pulses/moon.pkg'] = sha(package / 'moon.pkg')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, default=ROOT / 'validation/evidence/speed-first-candidate-revision7.json')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'validation/evidence/speed-first-pulses-manifest.json')
    parser.add_argument('--native-report', type=Path, default=ROOT / 'validation/evidence/speed-first-pulses-revision7.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'validation/evidence/speed-first-pulses-cross-revision7.json')
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--flac', type=Path, default=ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    parser.add_argument('--libflac')
    args = parser.parse_args()
    assert not args.report.exists() and not args.work.exists(), 'Preserve existing reports and isolated builds'
    identity = json.loads(args.identity.read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    native = json.loads(args.native_report.read_text(encoding='utf-8'))
    assert native['status'] == 'pass' and native['case_count'] == 32
    assert native['candidate_sha256'] == identity['cli']['sha256']
    assert native['manifest_sha256'] == sha(args.manifest)
    cli = ROOT / identity['cli']['path']
    assert sha(cli) == identity['cli']['sha256']
    cases = manifest['cases']
    native_cases = {case['name']: case for case in native['cases']}
    assert len(cases) == 32 and set(native_cases) == {case['name'] for case in cases}
    expected = {}
    for case in cases:
        result = native_cases[case['name']]
        assert result['pcm_sha256'] == case['pcm_sha256']
        path = Path(result['command'][3])
        assert sha(path) == result['encoded_sha256'], 'verified native output changed'
        expected[case['name']] = path.read_bytes()
    args.work.mkdir(parents=True)
    module = args.work / 'source'
    source_files = source_module(module, identity, cases)
    ref = LibFLAC(library(args.libflac))
    report = dict(status='running', identity_sha256=sha(args.identity), native_report_sha256=sha(args.native_report),
                  native_cli_sha256=sha(cli), manifest_sha256=sha(args.manifest), script_sha256=sha(Path(__file__)),
                  oracle_helper_sha256=sha(ROOT / 'scripts/validate_speed_first_pulses.py'),
                  source_files=source_files, targets=[],
                  toolchain=subprocess.check_output(['moon', 'version', '--all'], text=True),
                  node_version=subprocess.check_output(['node', '--version'], text=True).strip(),
                  reference=dict(version=version(ref), library_sha256=sha(Path(library(args.libflac))),
                                 cli_sha256=sha(args.flac)),
                  scope='32 frozen fixtures on JS and wasm-gc plus existing native32; exact cross-backend bytes and independent PCM/CRC/MD5; no timing claims')
    save(args.report, report)
    try:
        for target in ['js', 'wasm-gc']:
            build = args.work / 'build' / target
            command = ['moon', 'run', '--target', target, '--release', '--target-dir', str(build), 'validation/pulses']
            process = subprocess.run(command, cwd=module, capture_output=True, text=True, encoding='utf-8',
                                     errors='replace', timeout=1800)
            log = args.work / (target + '.log')
            log.write_text(process.stdout + process.stderr, encoding='utf-8')
            process.check_returncode()
            assert 'ERROR ' not in process.stdout
            streams = {name: bytes.fromhex(data) for name, data in re.findall(r'^ENCODED (\S+) ([0-9a-f]+)$', process.stdout, re.M)}
            assert set(streams) == set(expected), 'target omitted/added fixtures'
            extension = '.js' if target == 'js' else '.wasm'
            artifacts = list(build.rglob('pulses' + extension))
            assert len(artifacts) == 1, artifacts
            row = dict(target=target, command=command, exit_code=process.returncode,
                       log=str(log), artifact=dict(path=str(artifacts[0]), sha256=sha(artifacts[0])), cases=[])
            report['targets'].append(row)
            for case in cases:
                encoded = streams[case['name']]
                assert encoded == expected[case['name']], f'{target}: native byte mismatch for {case["name"]}'
                path = args.work / (target + '-' + case['name'] + '.flac')
                path.write_bytes(encoded)
                checked = validate(path, case, ref, args.flac)
                row['cases'].append(dict(name=case['name'], native_byte_identical=True, **checked))
                save(args.report, report)
            row['status'] = 'pass'
            print(target, '32/32 native bytes and independent PCM exact', flush=True)
        for name, digest in identity['sources'].items():
            assert sha(ROOT / name) == digest, 'production source changed while validating'
        for name, digest in source_files.items():
            assert sha(module / name) == digest, 'isolated source changed while validating'
        assert sha(cli) == report['native_cli_sha256']
        report.update(status='pass', new_stream_checks=64, native_stream_checks=32, total_backend_case_checks=96)
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save(args.report, report)


if __name__ == '__main__':
    main()
