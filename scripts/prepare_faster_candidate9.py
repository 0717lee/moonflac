"""Combine measured exact planner/CRC improvements with candidate8 search."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parents = []
    for name in ['candidate8', 'u32-plan-identity', 'crc-table-identity']:
        path = ROOT / f'validation/evidence/faster-than-libflac-{name}.json'
        record = json.loads(path.read_text())
        for source, digest in record['sources'].items():
            assert sha(ROOT / source) == digest, source
        parents.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
    destination = BASE / 'candidate9-source'
    assert not destination.exists()
    shutil.copytree(BASE / 'candidate8-source', destination,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__'))
    for source, names in [
        ('u32-plan-source', ['encoder_budget_plan.mbt',
                             'encoder_leaf_prefix_wbtest.mbt',
                             'encoder_lazy_tree_wbtest.mbt',
                             'encoder_fold_u32_wbtest.mbt']),
        ('crc-table-source', ['frame.mbt', 'crc_table_wbtest.mbt']),
    ]:
        for name in names:
            shutil.copy2(BASE / source / name, destination / name)
    with (BASE / 'candidate9-format.log').open('w', encoding='utf8') as log:
        for command in [['moon', 'fmt'], ['moon', 'fmt', '--check']]:
            subprocess.run(command, cwd=destination, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    files = {str(p.relative_to(destination)): sha(p)
             for p in destination.rglob('*') if p.is_file()
             and not any(part in {'_build', '.git', '.mooncakes'}
                         for part in p.relative_to(destination).parts)}
    report = dict(status='prepared_before_build', parents=parents,
                  source=str(destination.relative_to(ROOT)), files=files,
                  generator_sha256=sha(Path(__file__)),
                  policy='Candidate8 search unchanged; exact lazy-depth UInt32 '
                         'folded planner with Int64 totals and CRC tables. '
                         'No unchecked-index or output-buffer experiment included.')
    path = ROOT / 'validation/evidence/faster-than-libflac-candidate9-source.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
