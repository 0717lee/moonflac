"""Freeze the accepted hardening source and profile Rice phases in isolation."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_build/effort8'
EVIDENCE = ROOT / 'validation/evidence'
EXCLUDED = {'_build', '.mooncakes', '.git', 'node_modules', 'cache', 'results'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(historical=False, name=None):
    dest = WORK / (name or 'baseline')
    assert not dest.exists(), 'Never overwrite a frozen baseline'
    original = ROOT / ('validation/baselines/encoder_frame.pre-effort8.mbt.txt' if historical else 'encoder_frame.mbt')
    assert sha(original) == '509361274de453e812649cf9331a85898d177b76f7e81761be2d34f208ea273b'
    cli = ROOT / '_build/hardening/candidate/native/release/build/cmd/moonflac/moonflac.exe'
    if not historical:
        assert sha(cli) == '179b27506f7bc226750fe7efdddd4653d4df8c9f689b98a7787252c3a84e69fe'
    files = {}
    for folder, directories, names in os.walk(ROOT):
        directories[:] = [n for n in directories if n not in EXCLUDED]
        for name in names:
            path = Path(folder) / name
            rel = path.relative_to(ROOT)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            files[rel.as_posix()] = sha(path)
    shutil.copytree(ROOT / '.mooncakes', dest / '.mooncakes')
    if historical:
        shutil.copy2(original, dest / 'encoder_frame.mbt')
        files['encoder_frame.mbt'] = sha(original)
    else:
        shutil.copy2(cli, WORK / 'accepted-baseline.exe')
        shutil.copy2(original, ROOT / 'validation/baselines/encoder_frame.pre-effort8.mbt.txt')
    report = dict(files=files, accepted_cli_sha256='179b27506f7bc226750fe7efdddd4653d4df8c9f689b98a7787252c3a84e69fe',
                  reconstructed=historical,
                  toolchain=subprocess.check_output(['moon', 'version', '--all'], text=True))
    # Rebuilding a new cache must work even when published historical evidence
    # is already present; keep each reconstruction identity inside its copy.
    report_path = dest / 'source-identity.json' if historical else EVIDENCE / 'effort8-baseline.json'
    assert not report_path.exists(), 'Preserve previous identities'
    report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


def profile(candidate=False, name=None, allocation_probe=False):
    dest = WORK / (name or ('profile-candidate' if candidate else 'profile-baseline'))
    assert not dest.exists()
    shutil.copytree(WORK / 'baseline', dest, ignore=shutil.ignore_patterns('_build'))
    if candidate:
        shutil.copy2(ROOT / 'encoder_frame.mbt', dest / 'encoder_frame.mbt')
    pkg = dest / 'moon.pkg'
    pkg.write_text(pkg.read_text(encoding='utf-8').replace('import {', 'import {\n  "moonbitlang/core/bench",'), encoding='utf-8')
    path = dest / 'encoder_frame.mbt'
    text = path.read_text(encoding='utf-8')
    # Coarse regions: clock overhead is per plan/level, not per scalar/node.
    replacements = [
        ('let mut nodes : Array[EncoderRiceNode] = []', 'let stat_start = @bench.monotonic_clock_start()\n  let mut nodes : Array[EncoderRiceNode] = []'),
        ('let mut best : EncoderResidual = {', 'rice_profile[0] += @bench.monotonic_clock_end(stat_start)\n  let mut best : EncoderResidual = {'),
        ('for rice2 in [false, true] {', 'let decision_start = @bench.monotonic_clock_start()\n    for rice2 in [false, true] {'),
        ('if order == 0 {', 'rice_profile[1] += @bench.monotonic_clock_end(decision_start)\n    if order == 0 {'),
        ('for i = 0; i < nodes.length(); i = i + 2 {', 'let merge_start = @bench.monotonic_clock_start()\n    for i = 0; i < nodes.length(); i = i + 2 {'),
        ('order -= 1', 'rice_profile[2] += @bench.monotonic_clock_end(merge_start)\n    order -= 1'),
        ('let quotients = Array::make(31, 0L)', 'rice_allocations[0] += 1L\n    let quotients = Array::make(31, 0L)'),
        ('parts.push(part)', 'rice_allocations[1] += 1L\n        parts.push(part)'),
    ]
    if candidate:
        replacements = [
            ('let nodes : Array[EncoderRiceNode] = []', 'let stat_start = @bench.monotonic_clock_start()\n  let nodes : Array[EncoderRiceNode] = []'),
            ('let choices0 =', 'rice_profile[0] += @bench.monotonic_clock_end(stat_start)\n  let choices0 ='),
            ('let mut bits0 = 6L', 'let decision_start = @bench.monotonic_clock_start()\n    let mut bits0 = 6L'),
            ('offset += active', 'offset += active\n    rice_profile[1] += @bench.monotonic_clock_end(decision_start)'),
            ('for i = 0; i < active; i = i + 2 {', 'let merge_start = @bench.monotonic_clock_start()\n    for i = 0; i < active; i = i + 2 {'),
            ('order -= 1', 'rice_profile[2] += @bench.monotonic_clock_end(merge_start)\n    order -= 1'),
            ('workspace.push(Array::make(31, 0L))', 'rice_allocations[0] += 1L\n      workspace.push(Array::make(31, 0L))'),
            ('let choices = if best_rice2', 'rice_allocations[1] += (1 << best_order).to_int64()\n  let choices = if best_rice2'),
        ]
    for old, new in replacements:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    if allocation_probe:
        # Group allocation before the per-leaf statistics loop to time it with
        # one clock pair per plan, avoiding millions of clock calls. This is a
        # diagnostic variant, never a throughput benchmark of production.
        if candidate:
            allocation = '''let allocation_start = @bench.monotonic_clock_start()
  while workspace.length() < 1 << order {
    rice_allocations[0] += 1L
    workspace.push(Array::make(31, 0L))
  }
  rice_profile[3] += @bench.monotonic_clock_end(allocation_start)
  '''
        else:
            allocation = '''let allocation_start = @bench.monotonic_clock_start()
  let preallocated = Array::makei(1 << order, _ => Array::make(31, 0L))
  rice_profile[3] += @bench.monotonic_clock_end(allocation_start)
  '''
            text = text.replace('let quotients = Array::make(31, 0L)', 'let quotients = preallocated[p]')
        text = text.replace('let stat_start =', allocation + 'let stat_start =')
    path.write_text(text, encoding='utf-8')
    (dest / 'profile.mbt').write_text('''///|
let rice_profile : Array[Double] = Array::make(4, 0.0)
///|
let rice_allocations : Array[Int64] = [0L, 0L]
///|
pub fn rice_profile_report() -> Unit {
  println("RICE statistics_us=\\{rice_profile[0]} decision_us=\\{rice_profile[1]} merge_us=\\{rice_profile[2]} grouped_allocation_us=\\{rice_profile[3]} quotient_arrays=\\{rice_allocations[0]} partitions=\\{rice_allocations[1]}")
}
''', encoding='utf-8')
    main = dest / 'cmd/moonflac/main.mbt'
    main.write_text(main.read_text(encoding='utf-8').replace('@sys.exit(status)', '@flac.rice_profile_report()\n  @sys.exit(status)'), encoding='utf-8')
    subprocess.run(['moon', 'build', '--target', 'native', '--release'], cwd=dest, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'profile', 'profile-candidate'])
    parser.add_argument('--name')
    parser.add_argument('--allocation-probe', action='store_true')
    parser.add_argument('--historical', action='store_true', help='reconstruct the accepted algorithm from the archived source')
    args = parser.parse_args()
    if args.name and Path(args.name).name != args.name:
        parser.error('name must be a directory component')
    if args.historical and args.action != 'freeze':
        parser.error('--historical applies only to freeze')
    freeze(args.historical, args.name) if args.action == 'freeze' else profile(args.action == 'profile-candidate', args.name, args.allocation_probe)
