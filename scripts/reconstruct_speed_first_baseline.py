"""Reconstruct the accepted baseline from archived codec text and verified harnesses.

Creates a fresh source module only; does not build, install or time anything.
Then use the recorded MoonBit/MSVC toolchain and `moon update`, followed by
`moon build --target native --release`. Native executable hashes may change on
rebuild; original-set output hashes must match the accepted effort8 reports.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / '_build/speed-first/reconstructed')
    args = p.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / '_build'), 'Reconstruction must stay inside project _build'
    assert not out.exists(), 'Choose a fresh directory; existing work is preserved'
    frozen = json.loads((ROOT / 'validation/evidence/speed-first-baseline.json').read_text())
    sources = {}
    for source in (ROOT / 'validation/baselines/speed-first').glob('*.mbt.txt'):
        name = source.name.removesuffix('.txt')
        assert sha(source) == frozen['files'][name]
        sources[name] = source
    assert len(sources) == 17
    for name in frozen['files']:
        if name in ['moon.mod', 'moon.pkg', 'LICENSE'] or (
            name.startswith(('cmd/moonflac/', 'validation/benchmark8/')) and
            Path(name).suffix in ['.mbt', '.c', '.pkg']
        ):
            source = ROOT / name
            assert sha(source) == frozen['files'][name], name
            sources[name] = source
    for name, source in sources.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    # Module metadata requires its named README. Current usage prose does not
    # influence the archived codec or either executable harness.
    shutil.copy2(ROOT / 'README.md', out / 'README.md')
    report = dict(source_files={name: sha(source) for name, source in sources.items()},
                  accepted_toolchain=frozen['toolchain'], notes=__doc__)
    (out / 'reconstruction.json').write_text(json.dumps(report, indent=2)+'\n')
    print(out)


if __name__ == '__main__':
    main()
