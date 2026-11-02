"""Assemble the measured exact components and guarded variance ranking locally."""
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
    identities = []
    for name in ['candidate7', 'model-error-guard-identity']:
        path = ROOT / f'validation/evidence/faster-than-libflac-{name}.json'
        identity = json.loads(path.read_text())
        for source, digest in identity['sources'].items():
            assert sha(ROOT / source) == digest, source
        identities.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
    source = BASE / 'candidate8-source'
    assert not source.exists()
    shutil.copytree(BASE / 'candidate7-source', source,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__'))
    guarded = BASE / 'model-error-guard-source'
    shutil.copy2(guarded / 'encoder_search.mbt', source / 'encoder_search.mbt')
    shutil.copy2(guarded / 'encoder_variance_wbtest.mbt', source / 'encoder_variance_wbtest.mbt')
    shutil.copy2(BASE / 'prototype5-source/encoder_lpc_interchange_wbtest.mbt',
                 source / 'encoder_lpc_interchange_wbtest.mbt')

    # Retain the measured exact loop interchange; covariance scoring consumes
    # a small owned copy only when the existing shortlist policy needs it.
    lpc = (guarded / 'encoder_lpc.mbt').read_text()
    old = (source / 'encoder_lpc.mbt').read_text()
    begin = lpc.index('  let correlation = Array::make(')
    end = lpc.index('  let mut error = correlation[0]', begin)
    kernel_begin = old.index('  let correlation = FixedArray::make(')
    kernel_end = old.index('  let mut error = correlation[0]', kernel_begin)
    lpc = lpc[:begin] + old[kernel_begin:kernel_end] + '''  let variance_correlation = if variances is Some(_) {
    Array::makei(order_limit + 1, i => correlation[i])
  } else {
    []
  }
''' + lpc[end:]
    lpc = replace_once(lpc, 'let signal = Array::makei(n, i => {',
                       'let signal = FixedArray::makei(n, i => {')
    lpc = replace_once(lpc,
        'window_energy += (1.0 - position * position) * (1.0 - position * position)',
        'if variances is Some(_) {\n      window_energy += (1.0 - position * position) * (1.0 - position * position)\n    }')
    lpc = replace_once(lpc, 'encoder_lpc_variance(correlation, model, peak, window_energy)',
                       'encoder_lpc_variance(variance_correlation, model, peak, window_energy)')
    (source / 'encoder_lpc.mbt').write_text(lpc, encoding='utf8')

    frame = (source / 'encoder_frame.mbt').read_text()
    frame = replace_once(frame, '    let models = encoder_lpc_models(shifted, max_order)\n', '')
    frame = replace_once(frame, '    let candidates = if shortlist {', '''    let variances : Array[Double?] = []
    let models = encoder_lpc_models(shifted, max_order,
      variances=if shortlist { Some(variances) } else { None })
    let candidates = if shortlist {''')
    frame = replace_once(frame,
        'encoder_lpc_shortlist(shifted, models, depth, limit=models.length())',
        'encoder_lpc_variance_ranking(shifted, models, variances, depth)')
    (source / 'encoder_frame.mbt').write_text(frame, encoding='utf8')
    log = BASE / 'candidate8-format-before-build.log'
    with log.open('w', encoding='utf8') as output:
        subprocess.run(['moon', 'fmt'], cwd=source, stdout=output,
                       stderr=subprocess.STDOUT, check=True)
        # Normalize the imported leading comment before the project check;
        # this SDK's first formatting pass does not stabilize that separator.
        subprocess.run(['moonfmt', '-w', 'encoder_lpc_interchange_wbtest.mbt'],
                       cwd=source, stdout=output, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['moon', 'fmt', '--check'], cwd=source, stdout=output,
                       stderr=subprocess.STDOUT, check=True)
    files = {str(p.relative_to(source)): sha(p) for p in source.rglob('*')
             if p.is_file() and not any(part in {'_build', '.git', '.mooncakes'}
                                       for part in p.relative_to(source).parts)}
    record = dict(status='prepared_before_build', parents=identities,
                  source=str(source.relative_to(ROOT)), files=files,
                  generator_sha256=sha(Path(__file__)),
                  policy='C7 exact components plus guarded analytical ranking; existing eligibility/finalist count unchanged.')
    target = ROOT / 'validation/evidence/faster-than-libflac-candidate8-source.json'
    assert not target.exists()
    target.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
