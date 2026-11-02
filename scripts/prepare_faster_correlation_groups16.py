"""Prepare a sixteen-lag variant after the four-lag experiment regressed."""
import difflib
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity_path = ROOT / 'validation/evidence/faster-than-libflac-candidate28-correlation-groups-refined.json'
    identity = json.loads(identity_path.read_text())
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest, name
    source = ROOT / '_build/faster-than-libflac/candidate28-correlation-groups-refined-source'
    destination = ROOT / '_build/faster-than-libflac/candidate33-correlation-groups16-source'
    assert not destination.exists()
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        '_build', '.git', '__pycache__', 'checks', 'evidence', 'prebuild.json'))
    path = destination / 'encoder_lpc.mbt'
    original = path.read_text(encoding='utf8')
    start = original.index('  // Keep four independent lag accumulators')
    end = original.index('  while lag <= order_limit {', start)
    lines = [
        '  // Keep the existing interleaved loop when fewer than sixteen lags',
        '  // are available, rather than turning all short-order work into tails.',
        '  if order_limit < 15 {',
        '    for i = order_limit; i < n; i = i + 1 {',
        '      let value = signal.unsafe_get(i)',
        '      for lag = 0; lag <= order_limit; lag = lag + 1 {',
        '        correlation.unsafe_set(lag, correlation.unsafe_get(lag) + value * signal.unsafe_get(i - lag))',
        '      }',
        '    }',
        '    return correlation',
        '  }',
        '  // Preserve sixteen independent reduction chains to expose more',
        '  // instruction-level parallelism; each lag retains ascending i.',
        '  let mut lag = 0',
        '  while lag + 15 <= order_limit {',
    ]
    for k in range(16):
        lines.append(f'    let mut c{k} = correlation.unsafe_get(lag + {k})')
    lines += ['    for i = order_limit; i < n; i = i + 1 {',
              '      let value = signal.unsafe_get(i)']
    for k in range(16):
        lines.append(f'      c{k} += value * signal.unsafe_get(i - lag - {k})')
    lines.append('    }')
    for k in range(16):
        lines.append(f'    correlation.unsafe_set(lag + {k}, c{k})')
    lines += ['    lag += 16', '  }']
    modified = original[:start] + '\n'.join(lines) + '\n' + original[end:]
    path.write_text(modified, encoding='utf8')
    evidence = destination / 'evidence/correlation-groups16'
    evidence.mkdir(parents=True)
    (evidence / 'candidate.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), modified.splitlines(True), fromfile='C28', tofile='C33')), encoding='utf8')
    (evidence / 'README.md').write_text(
        'C28 four-lag measured ratio was1.022392 relative to C24; it is not selected. '
        'Its real AVX2 loop holds only one four-lane accumulator chain and assembles '
        'history vectors from scalar loads. This sixteen-lag variant tests whether '
        'additional independent chains help; neither the cause of the regression '
        'nor a speed benefit is claimed before measurement.\n\n'
        'Each accumulator starts from the unchanged triangular prefix and executes '
        'the same multiply then add for ascending i. Different lags do not interact. '
        '0<=lag+k<=order_limit<=i<n proves each read. The scalar tail is unchanged. '
        'Fewer than sixteen lags retain the original C24 interleaved loop. '
        'No floating reassociation, FMA setting, model/candidate policy or new cache. '
        'All C28 raw correlation bit-oracle, model/variance and existing tests are '
        'retained, including limits0..33 across group/tail boundaries. Source-only; '
        'format/build/tests and actual register/SIMD/performance validation pending.\n', encoding='utf8')
    files = {str(p.relative_to(destination)): sha(p) for p in destination.rglob('*')
             if p.is_file() and not any(x in {'.mooncakes', '_build'}
                                       for x in p.relative_to(destination).parts)}
    report = dict(status='source_only_not_formatted_or_tested',
                  source=str(destination.relative_to(ROOT)), files=files,
                  parent=dict(path=str(identity_path.relative_to(ROOT)), sha256=sha(identity_path)),
                  generator_sha256=sha(Path(__file__)))
    target = ROOT / 'validation/evidence/faster-than-libflac-candidate33-correlation-groups16-prepared.json'
    assert not target.exists()
    target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(target)


if __name__ == '__main__':
    main()
