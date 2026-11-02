"""Isolate the already-built quotient-column fast path without changing costs."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    identity_path = ROOT / 'validation/evidence/faster-than-libflac-candidate11-double.json'
    identity = json.loads(identity_path.read_text())
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest, name
    source = BASE / 'candidate11-double-source'
    destination = BASE / 'candidate16-ready-mask-source'
    assert not destination.exists()
    shutil.copytree(source, destination,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__', 'checks', 'evidence'))
    path = destination / 'encoder_budget_plan.mbt'
    text = path.read_text(encoding='utf8')
    text = replace_once(text, '  ready : Array[Bool]', '  mut ready_mask : UInt')
    text = replace_once(text, '    ready: Array::make(31, false),', '    ready_mask: 1U,')
    text = replace_once(text, '    if k > 0 && !scratch.ready[k] {',
                        '    if k > 0 && (scratch.ready_mask & (1U << k)) == 0U {')
    for name in ['k0', 'k1', 'k2']:
        text = replace_once(text, f'scratch.ready[{name}] = true',
                            f'scratch.ready_mask = scratch.ready_mask | (1U << {name})')
    text = replace_once(text,
        '  for k = 0; k < 31; k = k + 1 {\n    scratch.ready[k] = false\n  }',
        '  scratch.ready_mask = 1U')
    text = replace_once(text, 'fn encoder_prepare_leaf_prefixes(',
                        'fn encoder_prepare_leaf_prefixes_slow(')
    wrapper = '''///|
// Q(0) comes from the sum tree, so bit0 is always ready without a column.
// Legal windows satisfy 0<=low<=high<=30 and contain at most three k.
// The UInt mask has no signed-shift ambiguity. Reset it for every predictor;
// the slow path still overwrites every requested prefix before setting its bit.
fn encoder_prepare_leaf_prefixes(
  scratch : EncoderPlanScratch,
  size : Int,
  leaves : Int,
  low : Int,
  high : Int,
) -> Unit {
  let needed = ((1U << (high - low + 1)) - 1U) << low
  if (scratch.ready_mask & needed) != needed {
    encoder_prepare_leaf_prefixes_slow(scratch, size, leaves, low, high)
  }
}

'''
    text = replace_once(text, '///|\nfn encoder_prepare_leaf_prefixes_slow(',
                        wrapper + '///|\nfn encoder_prepare_leaf_prefixes_slow(')
    path.write_text(text, encoding='utf8')
    path = destination / 'encoder_leaf_prefix_wbtest.mbt'
    text = replace_once(path.read_text(encoding='utf8'),
                        'assert_false(scratch.ready[0])',
                        'assert_eq(scratch.prefixes[0].length(), 0)')
    path.write_text(text, encoding='utf8')
    with (BASE / 'candidate16-ready-mask-format.log').open('w', encoding='utf8') as log:
        for command in [['moon', 'fmt'], ['moon', 'fmt', '--check']]:
            subprocess.run(command, cwd=destination, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    files = {str(p.relative_to(destination)): sha(p)
             for p in destination.rglob('*') if p.is_file()
             and not any(part in {'_build', '.git', '.mooncakes'}
                         for part in p.relative_to(destination).parts)}
    report = dict(status='prepared_before_build',
                  parent=dict(path=str(identity_path.relative_to(ROOT)), sha256=sha(identity_path)),
                  source=str(destination.relative_to(ROOT)), files=files,
                  generator_sha256=sha(Path(__file__)),
                  policy='Same complete prefix columns, exact partition costs and ties. '
                         'Represent readiness by UInt bits0..30, isolate the small '
                         'all-ready guard from column construction. Q0 has no allocation.')
    path = ROOT / 'validation/evidence/faster-than-libflac-candidate16-ready-mask-source.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
