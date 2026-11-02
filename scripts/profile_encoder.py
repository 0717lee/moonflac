"""Freeze and instrument a separate source copy; never time production with probes.

python scripts/profile_encoder.py freeze
python scripts/profile_encoder.py profile
Native inclusive timings use MoonBit core bench's monotonic clock (microseconds).
Nested categories overlap; residual planning is contained in subframe search.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_build/hardening'
EVIDENCE = ROOT / 'validation/evidence'
EXCLUDED = {'_build', '.mooncakes', '.git', 'node_modules', 'cache', 'results'}


def freeze(historical=False):
    dest = WORK / 'baseline'
    if dest.exists():
        raise RuntimeError('Baseline already exists; preserve its identity')
    files = {}
    for folder, directories, names in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in EXCLUDED]
        for name in names:
            path = Path(folder) / name
            rel = path.relative_to(ROOT)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            files[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    shutil.copytree(ROOT / '.mooncakes', dest / '.mooncakes')
    if historical:
        original = ROOT / 'validation/baselines/encoder_frame.pre-hardening.mbt.txt'
        expected = '2cc4813f31410a661422057ab2d678a9a354166fda31c262e733a3225d8e6fb1'
        assert hashlib.sha256(original.read_bytes()).hexdigest() == expected
        shutil.copy2(original, dest / 'encoder_frame.mbt')
        files['encoder_frame.mbt'] = expected
    identity = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    report = dict(source_sha256=identity, files=files,
                  toolchain=subprocess.check_output(['moon', 'version', '--all'], text=True))
    (EVIDENCE / 'hardening-baseline-source.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Frozen', identity)
    subprocess.run(['moon', 'build', '--target', 'native', '--release'], cwd=dest, check=True)


FUNCTIONS = [
    ('encoder_frame.mbt', 'encoder_residual_plan', 'samples, predictor, max_partition'),
    ('encoder_frame.mbt', 'encoder_predictor', 'samples, coefficients, shift'),
    ('encoder_frame.mbt', 'encoder_subframe', 'samples, width, effort'),
    ('encoder_frame.mbt', 'encoder_write_subframe', 'out, sub'),
    ('encoder_lpc.mbt', 'encoder_lpc_models', 'samples, max_order'),
]


def instrument(candidate=False, name=None):
    dest = WORK / (name or ('profile-candidate' if candidate else 'profile'))
    if dest.exists():
        raise RuntimeError('Profile copy already exists')
    shutil.copytree(WORK / 'baseline', dest, ignore=shutil.ignore_patterns('_build'))
    if candidate:
        for file in ['encoder_frame.mbt', 'encoder_lpc.mbt']:
            shutil.copy2(ROOT / file, dest / file)
    package = dest / 'moon.pkg'
    package.write_text(package.read_text().replace('import {', 'import {\n  "moonbitlang/core/bench",'), encoding='utf-8')
    wrappers = ['///|\nlet profile_us : Array[Double] = Array::make(5, 0.0)',
                '///|\nlet profile_quotient_arrays : Array[Int64] = [0L]',
                '///|\nlet profile_calls : Array[Int] = Array::make(5, 0)']
    for index, (file, name, args) in enumerate(FUNCTIONS):
        path = dest / file
        text = path.read_text(encoding='utf-8')
        start = text.index('fn '+name+'(')
        end = text.index('{', start)
        signature = text[start:end]
        text = text[:start] + text[start:].replace('fn '+name+'(', 'fn '+name+'_profile_impl(', 1)
        path.write_text(text, encoding='utf-8')
        wrappers.append('///|\n'+signature+'{\n  let start = @bench.monotonic_clock_start()\n'
                        f'  let result = {name}_profile_impl({args})\n'
                        f'  profile_us[{index}] += @bench.monotonic_clock_end(start)\n'
                        f'  profile_calls[{index}] += 1\n  result\n}}')
    wrappers.append('///|\npub fn profile_report() -> Unit {\n'+''.join(
        f'  println("PROFILE {name} \\{{profile_us[{i}]}} \\{{profile_calls[{i}]}}")\n'
        for i, (_, name, _) in enumerate(FUNCTIONS))+
        '  println("PROFILE quotient_array_allocations \\{profile_quotient_arrays[0]}")\n}')
    frame = dest / 'encoder_frame.mbt'
    frame.write_text(frame.read_text(encoding='utf-8').replace(
        'let quotients = Array::make(31, 0L)',
        'profile_quotient_arrays[0] += 1L\n    let quotients = Array::make(31, 0L)').replace(
        'parents.push({', 'profile_quotient_arrays[0] += 1L\n      parents.push({'), encoding='utf-8')
    (dest / 'profile.mbt').write_text('\n\n'.join(wrappers)+'\n', encoding='utf-8')
    main = dest / 'cmd/moonflac/main.mbt'
    main.write_text(main.read_text(encoding='utf-8').replace('@sys.exit(status)', '@flac.profile_report()\n  @sys.exit(status)'), encoding='utf-8')
    subprocess.run(['moon', 'build', '--target', 'native', '--release'], cwd=dest, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'profile', 'profile-candidate'])
    parser.add_argument('--name',help='new snapshot directory name below _build/hardening')
    parser.add_argument('--historical',action='store_true',help='freeze with the preserved pre-hardening encoder implementation')
    args = parser.parse_args()
    if args.name and (Path(args.name).name != args.name or args.name in ['.','..']):
        parser.error('name must be one directory component')
    if args.historical and args.action != 'freeze':
        parser.error('--historical applies only to freeze')
    freeze(args.historical) if args.action == 'freeze' else instrument(args.action == 'profile-candidate', args.name)
