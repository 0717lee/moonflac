"""Attribute selected candidate costs without altering baseline profile evidence.

python scripts/profile_speed_first_candidate.py --name revision3
The inherited 'baseline' observation label means current uninstrumented CLI,
not the previous search policy. These shared-host samples are not a benchmark.
"""
import argparse
import json
import os
import re
import shutil
from pathlib import Path

import profile_speed_first as profiler

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_build/speed-first/profile-current'
REPORT = ROOT / 'validation/evidence/speed-first-profile-candidate.json'
IDENTITY = ROOT / 'validation/evidence/speed-first-profile-candidate-source.json'


def main(name, cli):
    global WORK, REPORT, IDENTITY
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
        raise ValueError('--name must be a single alphanumeric identifier')
    WORK = ROOT / '_build/speed-first' / ('profile-current-' + name)
    REPORT = ROOT / 'validation/evidence' / ('speed-first-profile-candidate-' + name + '.json')
    IDENTITY = ROOT / 'validation/evidence' / ('speed-first-profile-candidate-' + name + '-source.json')
    assert not WORK.exists() and not REPORT.exists() and not IDENTITY.exists(), 'Preserve existing candidate profile'
    original_cli = cli.resolve()
    assert original_cli.is_file()
    source = WORK / 'baseline'
    # Minimal complete source tree includes package manifests, native stubs and
    # tests. No generated build/cache/evidence or previous experiment copies.
    exclusions = {'_build', '.mooncakes', '.git', 'node_modules', 'cache',
                  'isolate_build', 'results', 'evidence', 'docs', 'scripts', 'playground', '.github'}
    hashes = {}
    for folder, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in exclusions]
        for name in files:
            path = Path(folder) / name
            if path.suffix not in ['.mbt', '.mbti', '.c', '.h'] and name not in ['moon.mod', 'moon.pkg', 'moon.mod.json', 'moon.pkg.json', 'README.md', 'LICENSE']:
                continue
            relative = path.relative_to(ROOT)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            hashes[relative.as_posix()] = profiler.sha(path)
    shutil.copytree(ROOT / '.mooncakes', source / '.mooncakes')
    shutil.copy2(original_cli, WORK / 'accepted-baseline.exe')
    identity = dict(revision=name, files=hashes, current_cli=str(original_cli),
                    current_cli_sha256=profiler.sha(original_cli),
                    runner_sha256=profiler.sha(Path(__file__)),
                    inherited_profiler_sha256=profiler.sha(ROOT / 'scripts/profile_speed_first.py'))
    profiler.save(IDENTITY, identity)
    profiler.WORK = WORK
    profiler.DEST = WORK / 'instrumented'
    profiler.REPORT = REPORT
    profiler.CODEGEN = WORK / 'unused-codegen.json'
    shortlist_source = (source / 'encoder_search.mbt').read_text(encoding='utf-8')
    shortlist_signature = shortlist_source.split('fn encoder_lpc_shortlist(', 1)[1].split('{', 1)[0]
    shortlist_args = 'samples, models, depth' + (', limit~' if 'limit?' in shortlist_signature else '')
    profiler.FUNCTIONS = profiler.FUNCTIONS + [
        ('encoder_search.mbt', 'encoder_lpc_shortlist', shortlist_args),
        ('encoder_search.mbt', 'encoder_sparse_partition_limit', 'samples, predictor'),
    ]
    # Compilation flags and baseline C were already captured by the prior task.
    # Reusing its independent attribution runner does not rerun that investigation.
    profiler.codegen = lambda: None
    profiler.main()
    report = json.loads(REPORT.read_text(encoding='utf-8'))
    report.update(subject='Selected candidate ' + name,
                  comparison='Current uninstrumented CLI versus identically sourced instrumented candidate; no old-policy speed comparison',
                  candidate_source_identity_sha256=profiler.sha(IDENTITY),
                  adapter_script_sha256=profiler.sha(Path(__file__)))
    for relative, digest in hashes.items():
        assert profiler.sha(ROOT / relative) == digest, 'source changed during profile: ' + relative
    assert profiler.sha(original_cli) == identity['current_cli_sha256'], 'CLI changed during profile'
    report['source_and_cli_unchanged'] = True
    profiler.save(REPORT, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--cli', type=Path, default=ROOT / '_build/speed-first/candidate/native/release/build/cmd/moonflac/moonflac.exe')
    args = parser.parse_args()
    main(args.name, args.cli)
