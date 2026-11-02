"""Profile the frozen speed-first baseline in a disposable instrumented copy.

python scripts/profile_speed_first.py
No production files or prior-phase evidence are changed. Coarse inclusive
probes measure successful calls; nested buckets overlap. This is attribution,
not a controlled speedup experiment.
"""
import argparse
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_build/speed-first'
DEST = WORK / 'profile-baseline'
REPORT = ROOT / 'validation/evidence/speed-first-profile.json'
CODEGEN = ROOT / 'validation/evidence/speed-first-native-codegen.json'
FUNCTIONS = [
    ('encoder_frame.mbt', 'encode_frame', 'format, planes, number, variable_block, effort'),
    ('encoder_frame.mbt', 'encoder_subframe', 'samples, width, effort'),
    ('encoder_lpc.mbt', 'encoder_lpc_models', 'samples, max_order'),
    ('encoder_frame.mbt', 'encoder_predictor', 'samples, coefficients, shift'),
    ('encoder_frame.mbt', 'encoder_residual_plan', 'samples, predictor, max_partition, workspace~'),
    ('encoder_frame.mbt', 'encoder_write_subframe', 'out, sub'),
    ('md5.mbt', 'Md5::update', 'self, bytes'),
    ('md5.mbt', 'md5_update_frame', 'state, frame'),
    ('wav.mbt', 'frame_pcm', 'frame, wav~'),
    ('pcm_input.mbt', 'PcmInput::next', 'self'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def instrument():
    assert not DEST.exists() and not REPORT.exists() and not CODEGEN.exists(), 'Preserve earlier probe results'
    shutil.copytree(WORK / 'baseline', DEST,
                    ignore=shutil.ignore_patterns('_build', 'isolate_build', 'cache', 'node_modules'))
    for package in [DEST / 'moon.pkg', DEST / 'cmd/moonflac/moon.pkg']:
        package.write_text(package.read_text(encoding='utf-8').replace('import {', 'import {\n  "moonbitlang/core/bench",'), encoding='utf-8')
    wrappers = [f'///|\nlet profile_us : Array[Double] = Array::make({len(FUNCTIONS)}, 0.0)',
                f'///|\nlet profile_calls : Array[Int] = Array::make({len(FUNCTIONS)}, 0)']
    for index, (file, name, args) in enumerate(FUNCTIONS):
        path = DEST / file
        text = path.read_text(encoding='utf-8')
        start = text.index('fn ' + name + '(')
        if text[max(0, start - 4):start] == 'pub ':
            start -= 4
        end = text.index('{', start)
        signature = text[start:end]
        impl = name + '_profile_impl'
        text = text[:start] + text[start:].replace('fn ' + name + '(', 'fn ' + impl + '(', 1)
        path.write_text(text, encoding='utf-8')
        wrappers.append('///|\n' + signature + '{\n  let started = @bench.monotonic_clock_start()\n'
                        f'  let result = {impl}({args})\n'
                        f'  profile_us[{index}] += @bench.monotonic_clock_end(started)\n'
                        f'  profile_calls[{index}] += 1\n  result\n}}')
    wrappers.append('///|\npub fn profile_report() -> Unit {\n' + ''.join(
        f'  println("PROFILE {name} \\{{profile_us[{i}]}} \\{{profile_calls[{i}]}}")\n'
        for i, (_, name, _) in enumerate(FUNCTIONS)) + '''
  let outer = @bench.monotonic_clock_start()
  let mut measured = 0.0
  for i = 0; i < 100000; i = i + 1 {
    let started = @bench.monotonic_clock_start()
    measured += @bench.monotonic_clock_end(started)
  }
  println("PROBE_CLOCK 100000 \\{measured} \\{@bench.monotonic_clock_end(outer)}")
}
''')
    (DEST / 'profile.mbt').write_text('\n\n'.join(wrappers), encoding='utf-8')
    main = DEST / 'cmd/moonflac/main.mbt'
    text = main.read_text(encoding='utf-8')
    text = text.replace('extern "C" fn read_chunk(', 'extern "C" fn read_chunk_profile_impl(')
    text += '''
///|
let cli_profile_us : Array[Double] = [0.0, 0.0]
///|
let cli_profile_calls : Array[Int] = [0, 0]
///|
fn read_chunk(bytes : FixedArray[Byte], length : Int) -> Int {
  let started = @bench.monotonic_clock_start()
  let result = read_chunk_profile_impl(bytes, length)
  cli_profile_us[0] += @bench.monotonic_clock_end(started)
  cli_profile_calls[0] += 1
  result
}
'''
    text = text.replace('fn execute_encode(', 'fn execute_encode_profile_impl(', 1)
    text += '''
///|
fn execute_encode(options : Options) -> Unit raise {
  let started = @bench.monotonic_clock_start()
  execute_encode_profile_impl(options)
  cli_profile_us[1] += @bench.monotonic_clock_end(started)
  cli_profile_calls[1] += 1
}
'''
    text = text.replace('@sys.exit(status)', '''@flac.profile_report()
  println("PROFILE cli_read_chunk \\{cli_profile_us[0]} \\{cli_profile_calls[0]}")
  println("PROFILE cli_execute_encode \\{cli_profile_us[1]} \\{cli_profile_calls[1]}")
  @sys.exit(status)''')
    main.write_text(text, encoding='utf-8')
    with (WORK / 'profile-build.log').open('w', encoding='utf-8') as log:
        subprocess.run(['moon', '-v', 'build', '--target', 'native', '--release'], cwd=DEST,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)


def codegen():
    log = WORK / 'profile-codegen-build.log'
    target = WORK / 'profile-codegen-build'
    actual_commands = {}
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(['moon', '-v', 'build', '--target', 'native', '--release',
                                    '--target-dir', str(target), 'cmd/moonflac'],
                                   cwd=WORK / 'baseline', stdout=stream, stderr=subprocess.STDOUT)
        monitored = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                children = monitored.children(recursive=True)
            except psutil.NoSuchProcess:
                children = []
            for child in children:
                try:
                    if child.name().lower() in ['cl.exe', 'clang.exe', 'gcc.exe', 'link.exe']:
                        actual_commands[str(child.pid)] = dict(pid=child.pid, executable=child.exe(), command=child.cmdline())
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(.005)
        assert process.returncode == 0, f'codegen build failed: {log}'
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    commands = [dict(line=i + 1, text=line) for i, line in enumerate(lines)
                if ('cl.exe' in line.lower() or ' /O' in line or ' -O' in line or 'moon_c' in line)]
    files = list((target / 'native/release').rglob('moonflac.c'))
    assert files, 'native generated C missing'
    # Retain bounded excerpts and actual line numbers, not guesses from source.
    evidence = []
    patterns = {'allocation': r'moonbit_make_array|moonbit_malloc|moonbit_make_fixed_array|moonbit_alloc',
                'reference_count': r'moonbit_(?:inc|dec)ref',
                'bounds': r'moonbit_checkbound|moonbit_bounds|moonbit_array_bound|moonbit_panic|moonbit_get_array_length',
                'rice_function': r'encoder__residual__plan|encoder__rice__parameter',
                'lpc_function': r'encoder__lpc__models|encoder__predictor'}
    for path in files:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
        categories = {}
        for name, pattern in patterns.items():
            hits = [(i, line) for i, line in enumerate(content) if re.search(pattern, line)]
            categories[name] = dict(total_matching_lines=len(hits), examples=[dict(line=i + 1, text=line) for i, line in hits[:12]])
        evidence.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), lines=len(content), categories=categories))
    save(CODEGEN, dict(status='observed', build_log=str(log.relative_to(ROOT)), compiler_command_evidence=commands,
                       observed_compiler_processes=list(actual_commands.values()),
                       generated_c=evidence, source='Frozen uninstrumented speed-first baseline, separately built for actual compiler command observation.',
                       limitations=['Static generated-C counts are not executed-operation counts or attribution of wall time.',
                                    'C compiler optimization may eliminate generated bounds checks; no machine-code dynamic cost claim.']))
    enrich_codegen()


def enrich_codegen():
    report = json.loads(CODEGEN.read_text(encoding='utf-8'))
    path = ROOT / report['generated_c'][0]['path']
    lines = path.read_text(encoding='utf-8').splitlines()
    patterns = {
        'md5_shifts_allocation_each_block': r'shifts__buf.*moonbit_make_int32_array_raw\(16\)',
        'md5_constants_allocation_each_block': r'constants__buf.*moonbit_make_int32_array_raw\(64\)',
        'md5_constants_release_each_block': r'moonbit_decref\(.*constants__buf',
        'md5_shifts_release_each_block': r'moonbit_decref\(.*shifts__buf',
        'frame_pcm_closure_allocation_per_frame': r'frame__pcm.*moonbit_malloc',
        'rice_workspace_reference_increment': r'moonbit_incref\(.*quotients',
    }
    report['hot_path_snippets'] = {}
    for name, pattern in patterns.items():
        hits = [i for i, line in enumerate(lines) if re.search(pattern, line)]
        report['hot_path_snippets'][name] = [dict(line=i + 1, context_start=max(0, i - 2) + 1,
                                                 context=lines[max(0, i - 2):i + 4]) for i in hits[:5]]
    report['interpretation'] = [
        'Actual MSVC core compile /O2 and /MT were observed, so the accepted binary was not accidentally built without native optimization.',
        'MD5 shifts and constants use fresh runtime arrays within Md5::block, with per-call initialization and decref; they are not emitted as static tables.',
        'frame_pcm allocates one frame buffer and one closure per call; its byte callback performs divisions, modulo and bounds-checked planar reads, not one heap allocation per sample.',
        'Rice workspace reuses quotient arrays but generated C still contains reference counting, bounds branches and node allocations; static presence alone does not measure their runtime share.',
        'Observed child command paths can have ACP decoding artifacts for Chinese characters; executable identity and ASCII compiler flags were retained verbatim.'
    ]
    save(CODEGEN, report)


def main():
    instrument()
    codegen()
    baseline = WORK / 'accepted-baseline.exe'
    candidate = DEST / '_build/native/release/build/cmd/moonflac/moonflac.exe'
    manifest_path = ROOT / 'validation/cache/effort8-benchmark/core-inputs.json'
    cases = [c for c in json.loads(manifest_path.read_text(encoding='utf-8'))['cases']
             if c['name'] in ['noise-16-2', 'ar-24-2', 'recording-28', 'silence-16-2', 'maximum-block-32-8']]
    assert len(cases) == 5
    report = dict(status='running', cases=[], baseline_cli_sha256=sha(baseline),
                  instrumented_cli_sha256=sha(candidate), manifest_sha256=sha(manifest_path),
                  baseline_frame_sha256=sha(WORK / 'baseline/encoder_frame.mbt'),
                  runner_sha256=sha(Path(__file__)),
                  protocol='Five existing input cases, two baseline/instrumented observations each; nested coarse probes; attribution only.',
                  limitations=['Unpinned shared host; allowed to overlap implementation/builds; wall deltas are probe-cost observations, not speedup.',
                               'Inclusive categories overlap; clocks and wrapper calls perturb optimizer/inlining.',
                               'Md5::update included by md5_update_frame; frame_pcm measured separately; CLI read is buffered OS read only.',
                               'Instrumented process wall time includes the post-encode 100000-iteration clock calibration; wall delta is not pure probe overhead.',
                               'Repeated tiny clock experiment approximates clock cost only, not wrapper/optimizer effects.'])
    save(REPORT, report)
    for case in cases:
        entry = dict(case, observations=[])
        report['cases'].append(entry)
        for repetition in range(2):
            row = dict(repetition=repetition)
            outputs = {}
            for label, binary in [('baseline', baseline), ('instrumented', candidate)]:
                output = WORK / f'profile-{case["name"]}-{label}.flac'
                command = [str(binary), 'encode', str(ROOT / case['path']), str(output), '--raw', '--sample-rate', str(case['rate']),
                           '--channels', str(case['channels']), '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', '8']
                start = time.perf_counter()
                result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
                elapsed = time.perf_counter() - start
                log = WORK / f'profile-{case["name"]}-{label}-{repetition}.log'
                log.write_text(result.stdout + result.stderr, encoding='utf-8')
                row[label] = dict(wall_seconds=elapsed, command=command, log=str(log.relative_to(ROOT)), output_sha256=sha(output))
                outputs[label] = output.read_bytes()
                if label == 'instrumented':
                    profiles = {name: dict(microseconds=float(us), calls=int(n))
                                for name, us, n in re.findall(r'^PROFILE (\S+) ([\d.eE+-]+) (\d+)$', result.stdout, re.M)}
                    assert len(profiles) == len(FUNCTIONS) + 2, result.stdout
                    total = profiles['cli_execute_encode']['microseconds']
                    for item in profiles.values():
                        item['percent_cli_execute_encode'] = item['microseconds'] / total * 100
                    row['profiles'] = profiles
                    probe = re.search(r'^PROBE_CLOCK (\d+) ([\d.eE+-]+) ([\d.eE+-]+)$', result.stdout, re.M)
                    assert probe, result.stdout
                    row['clock_calibration'] = dict(iterations=int(probe[1]), inner_us=float(probe[2]), outer_us=float(probe[3]))
            assert outputs['baseline'] == outputs['instrumented'], 'probes changed bitstream'
            row['bitstream_identical'] = True
            row['instrumented_wall_delta_percent'] = 100 * (row['instrumented']['wall_seconds'] / row['baseline']['wall_seconds'] - 1)
            entry['observations'].append(row)
            save(REPORT, report)
        entry['median_percent_cli_execute_encode'] = {
            name: statistics.median(row['profiles'][name]['percent_cli_execute_encode'] for row in entry['observations'])
            for name in entry['observations'][0]['profiles']}
        print(case['name'], entry['median_percent_cli_execute_encode'], flush=True)
    report['status'] = 'pass'
    save(REPORT, report)


def profile_md5():
    destination = WORK / 'profile-md5'
    evidence = ROOT / 'validation/evidence/speed-first-profile-md5.json'
    assert not destination.exists() and not evidence.exists()
    shutil.copytree(DEST, destination, ignore=shutil.ignore_patterns('_build', 'isolate_build', 'cache', 'node_modules'))
    path = destination / 'md5.mbt'
    text = path.read_text(encoding='utf-8').replace('fn Md5::block(', 'fn Md5::block_profile_impl(', 1)
    text += '''
///|
let md5_block_us : Array[Double] = [0.0]
///|
let md5_block_calls : Array[Int] = [0]
///|
fn Md5::block(self : Md5, bytes : Array[Byte]) -> Unit {
  let started = @bench.monotonic_clock_start()
  self.block_profile_impl(bytes)
  md5_block_us[0] += @bench.monotonic_clock_end(started)
  md5_block_calls[0] += 1
}
'''
    path.write_text(text, encoding='utf-8')
    path = destination / 'profile.mbt'
    path.write_text(path.read_text(encoding='utf-8').replace('  let outer =',
                    '  println("PROFILE Md5::block \\{md5_block_us[0]} \\{md5_block_calls[0]}")\n  let outer ='), encoding='utf-8')
    with (WORK / 'profile-md5-build.log').open('w', encoding='utf-8') as log:
        subprocess.run(['moon', 'build', '--target', 'native', '--release', 'cmd/moonflac'],
                       cwd=destination, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    binary = destination / '_build/native/release/build/cmd/moonflac/moonflac.exe'
    manifest = json.loads((ROOT / 'validation/cache/effort8-benchmark/core-inputs.json').read_text(encoding='utf-8'))
    report = dict(status='running', runner_sha256=sha(Path(__file__)), binary_sha256=sha(binary), cases=[],
                  limitations=['Additional clock pair on every 64-byte MD5 block perturbs short-operation timing.',
                               'Call counts are exact; allocation interpretation comes from separately captured uninstrumented C.',
                               'No controlled comparison of code optimizations is performed.'])
    for case in manifest['cases']:
        if case['name'] not in ['silence-16-2', 'maximum-block-32-8']:
            continue
        output = WORK / f'profile-md5-{case["name"]}.flac'
        command = [str(binary), 'encode', str(ROOT / case['path']), str(output), '--raw', '--sample-rate', str(case['rate']),
                   '--channels', str(case['channels']), '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', '8']
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
        (WORK / f'profile-md5-{case["name"]}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        profiles = {name: dict(microseconds=float(us), calls=int(n))
                    for name, us, n in re.findall(r'^PROFILE (\S+) ([\d.eE+-]+) (\d+)$', result.stdout, re.M)}
        expected_calls = (case['pcm_bytes'] + 8) // 64 + 1
        assert profiles['Md5::block']['calls'] == expected_calls
        assert output.read_bytes() == (WORK / f'profile-{case["name"]}-baseline.flac').read_bytes()
        report['cases'].append(dict(case, profiles=profiles, bitstream_identical=True,
                                   md5_block_calls_including_padding=expected_calls,
                                   per_block_constant_arrays_from_generated_c=2,
                                   constant_array_allocations=2 * expected_calls))
        save(evidence, report)
    report['status'] = 'pass'
    save(evidence, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['profile', 'md5', 'codegen'], default='profile')
    action = parser.parse_args().action
    {'profile': main, 'md5': profile_md5, 'codegen': codegen}[action]()
