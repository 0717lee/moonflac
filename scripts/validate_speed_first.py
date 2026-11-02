"""Speed-first correctness gates with isolated reports and generated oracle sources.

python scripts/validate_speed_first.py --revision 3

Reuses the established independent encoder oracles without modifying their
source, accepted reports, generated validation/encoder package, or old caches.
Run after production changes are frozen, separately from controlled benchmarks.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / '_build/speed-first/checks'
REPORTS = ROOT / 'validation/evidence/speed-first-checks'
BUILD = LOGS / 'build'
CLI = BUILD / 'native/release/build/cmd/moonflac/moonflac.exe'
FLAC = ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def oracle_worker(action, flac, ffmpeg):
    import validate_encoder as oracle
    from types import SimpleNamespace

    oracle.EVIDENCE = REPORTS
    oracle.WORK = LOGS / 'oracle-work'
    oracle.WORK.mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(cli=CLI, flac=flac, ffmpeg=ffmpeg, match='', timeout=120,
                           report=REPORTS / 'encoder-native.json', log=LOGS / 'native-test.log')
    if LOGS.name == 'final-artifact':
        args.log = LOGS.parent / 'native-test.log'
    ref = oracle.LibFLAC(oracle.library(None))
    if action == 'cross':
        # cross_backend generates its executable and formats it. Give it a
        # minimal isolated module so original source and old builds stay intact.
        isolated = LOGS / 'cross-source'
        isolated.mkdir(parents=True, exist_ok=False)
        copied = {}
        for path in list(ROOT.glob('*.mbt')) + [ROOT / name for name in ['moon.mod', 'moon.pkg', 'README.md', 'LICENSE']]:
            if path.name.endswith(('_test.mbt', '_wbtest.mbt')):
                continue
            shutil.copy2(path, isolated / path.name)
            copied[path.name] = sha(path)
        shutil.copytree(ROOT / '.mooncakes', isolated / '.mooncakes')
        cases = json.loads(oracle.MANIFEST.read_text(encoding='utf-8'))
        for case in cases:
            case['path'] = str((ROOT / case['path']).resolve())
        manifest = LOGS / 'cross-manifest.json'
        save(manifest, cases)
        save(REPORTS / 'cross-source.json', copied)
        oracle.MANIFEST = manifest
        oracle.ROOT = isolated
        passed = oracle.cross_backend(ref, args)
    elif action == 'compare':
        passed = oracle.compare(ref, args)
    elif action == 'forced':
        passed = oracle.forced(ref, args)
    else:
        raise ValueError(action)
    if not passed:
        raise SystemExit(1)


def sources():
    files = list(ROOT.glob('*.mbt')) + list((ROOT / 'cmd/moonflac').glob('*'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in files
            if p.is_file() and not p.name.endswith(('_test.mbt', '_wbtest.mbt'))}


def main():
    global LOGS, REPORTS, BUILD, CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', type=int, required=True, choices=[3, 4, 7])
    parser.add_argument('--cli', type=Path)
    parser.add_argument('--cli-only', action='store_true', help='Validate the final frozen CLI artifact, reusing the completed source cross-backend gate')
    parser.add_argument('--oracle-worker', choices=['compare', 'forced', 'cross'], help=argparse.SUPPRESS)
    parser.add_argument('--resume-after-format', action='store_true', help='Retain passed gates and rerun failed format after formatting-only correction')
    parser.add_argument('--flac', type=Path, default=FLAC)
    parser.add_argument('--ffmpeg', type=Path, default=Path(shutil.which('ffmpeg') or 'ffmpeg'))
    args = parser.parse_args()
    LOGS = ROOT / f'_build/speed-first/checks-revision{args.revision}'
    REPORTS = ROOT / f'validation/evidence/speed-first-checks-revision{args.revision}'
    BUILD = LOGS / 'build'
    CLI = BUILD / 'native/release/build/cmd/moonflac/moonflac.exe'
    if args.cli:
        CLI = args.cli.resolve()
    if args.cli_only:
        assert args.cli and not args.resume_after_format
        LOGS = LOGS / 'final-artifact'
        REPORTS = REPORTS / 'final-artifact'
    if args.oracle_worker:
        oracle_worker(args.oracle_worker, args.flac.resolve(), args.ffmpeg)
        return
    LOGS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not args.resume_after_format and ((REPORTS / 'commands.json').exists() or (REPORTS / 'acceptance.json').exists()):
        raise FileExistsError('Preserve existing speed-first validation reports; explicitly archive them before a rerun')
    before = sources()
    initial_cli_sha256 = sha(CLI) if args.cli else None
    identity = ROOT / f'validation/evidence/speed-first-candidate-revision{args.revision}.json'
    frozen = json.loads(identity.read_text(encoding='utf-8'))
    assert all(before[name] == value for name, value in frozen['sources'].items()), 'candidate is not frozen revision'
    records = []
    previous = None
    if args.resume_after_format:
        previous = json.loads((REPORTS / 'acceptance.json').read_text(encoding='utf-8'))
        records = previous['commands']
        assert records[-1]['name'] == 'format' and records[-1]['status'] == 'fail'
        assert all(r['status'] == 'pass' for r in records[:-1])
    final = dict(status='running', codec_sources=before, runner_sha256=sha(Path(__file__)),
                 revision=args.revision, frozen_identity_sha256=sha(identity),
                 oracle_sha256=sha(ROOT / 'scripts/validate_encoder.py'), commands=records,
                 scope='speed-first candidate policy and MD5 changes; three backend package gates, independent encoder oracles, encoder and decoder CLI contracts; no benchmarks or holdout runs')
    if previous:
        final['format_resume_previous_sources'] = previous['codec_sources']
        final['format_resume_previous_identity_sha256'] = previous['frozen_identity_sha256']
        final['format_resume_previous_runner_sha256'] = previous['runner_sha256']
        final['format_resume_note'] = 'Passed backend gates retained from pre-format source; owner applied only moonfmt to encoder_search.mbt.'
        changed = [name for name in before if before[name] != previous['codec_sources'].get(name)]
        assert set(changed) <= {'encoder_search.mbt'}, changed

    def run(name, command):
        if any(r['name'] == name and r['status'] == 'pass' for r in records):
            return
        start = time.monotonic()
        record = dict(name=name, command=[str(x) for x in command], status='running')
        records.append(record)
        save(REPORTS / 'commands.json', records)
        try:
            log_path = LOGS / (name + (f'-attempt{sum(r["name"] == name for r in records)}' if sum(r['name'] == name for r in records) > 1 else '') + '.log')
            record['log'] = str(log_path)
            with log_path.open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
            record.update(status='pass' if result.returncode == 0 else 'fail', exit_code=result.returncode)
            result.check_returncode()
        except BaseException as error:
            record.update(status='fail', error=repr(error))
            raise
        finally:
            record['seconds'] = time.monotonic() - start
            save(REPORTS / 'commands.json', records)
        print(name, record['exit_code'], flush=True)

    save(REPORTS / 'acceptance.json', final)
    try:
        for target in ([] if args.cli_only else ['native', 'js', 'wasm-gc']):
            for action in ['check', 'test', 'build']:
                command = ['moon', action, '--target', target, '--target-dir', str(BUILD)]
                if action == 'build':
                    command.append('--release')
                run(target + '-' + action, command)
        if not args.cli_only:
            run('format', ['moon', 'fmt', '--check', '--target-dir', str(LOGS / 'format')])
        if previous:
            run('native-cli-build-after-format', ['moon', 'build', 'cmd/moonflac', '--target', 'native', '--release', '--target-dir', str(BUILD)])
        run('encoder-cli', [sys.executable, '-X', 'utf8', 'cmd/test_encoder_cli.py', '--cli', str(CLI), '--flac', str(args.flac)])
        run('decoder-cli', [sys.executable, '-X', 'utf8', 'cmd/test_cli.py', '--cli', str(CLI), '--flac', str(args.flac)])
        for action in (['compare', 'forced'] if args.cli_only else ['compare', 'forced', 'cross']):
            run('oracle-' + action, [sys.executable, '-X', 'utf8', str(Path(__file__)), '--oracle-worker', action,
                                     '--revision', str(args.revision),
                                     '--cli', str(CLI), *(['--cli-only'] if args.cli_only else []),
                                     '--flac', str(args.flac), '--ffmpeg', str(args.ffmpeg)])
        assert sources() == before, 'production sources changed while validation ran'
        if args.cli:
            assert sha(CLI) == initial_cli_sha256, 'frozen CLI artifact changed during checks'
            final['cli_initial_sha256'] = initial_cli_sha256
        native = json.loads((REPORTS / 'encoder-native.json').read_text(encoding='utf-8'))
        forced = json.loads((REPORTS / 'encoder-forced.json').read_text(encoding='utf-8'))
        cross_path = (REPORTS.parent if args.cli_only else REPORTS) / 'encoder-backends.json'
        cross = json.loads(cross_path.read_text(encoding='utf-8'))
        if args.cli_only:
            assert sha(CLI) == initial_cli_sha256, 'final CLI artifact changed during checks'
            final['cli_initial_sha256'] = initial_cli_sha256
            final['reused_cross_backend_report'] = str(cross_path)
            final['reused_cross_backend_sha256'] = sha(cross_path)
        assert len(native['cases']) == 328, 'incomplete native matrix'
        assert sum(c.get('ffmpeg') == 'exact PCM pass' for c in native['cases']) == 327, 'incomplete FFmpeg audio matrix'
        assert len(forced['cases']) == 137, 'incomplete forced writer matrix'
        assert len(cross['targets']) == 3 and all(len(t['cases']) == 276 for t in cross['targets']), 'incomplete cross-backend matrix'
        final.update(status='pass', cli_sha256=sha(CLI), counts=dict(native=len(native['cases']), ffmpeg_audio=sum(c.get('ffmpeg') == 'exact PCM pass' for c in native['cases']),
                     forced=len(forced['cases']), cross_backend=sum(len(t['cases']) for t in cross['targets'])),
                     reports={p.name: sha(p) for p in REPORTS.glob('*.json') if p.name != 'acceptance.json'})
    except BaseException as error:
        final.update(status='fail', error=repr(error))
        raise
    finally:
        save(REPORTS / 'acceptance.json', final)


if __name__ == '__main__':
    main()
