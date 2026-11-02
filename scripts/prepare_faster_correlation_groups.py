"""Prepare an isolated exact-order autocorrelation accumulator experiment."""
import difflib
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity_path = ROOT / 'validation/evidence/faster-than-libflac-candidate24-fixed-seed.json'
    identity = json.loads(identity_path.read_text())
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest, name
    source = BASE / 'candidate24-fixed-seed-source'
    destination = BASE / 'candidate28-correlation-groups-refined-source'
    assert not destination.exists()
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        '_build', '.git', '__pycache__', 'checks', 'evidence'))
    path = destination / 'encoder_lpc.mbt'
    original = path.read_text(encoding='utf8')
    start = original.index('  for i = order_limit; i < n; i = i + 1 {')
    end = original.index('  let variance_correlation', start)
    replacement = '''  // Keep four independent lag accumulators live across the sample loop.
  // Every lag still visits the same ascending i, with separate multiply/add.
  let mut lag = 0
  while lag + 3 <= order_limit {
    let mut a = correlation.unsafe_get(lag)
    let mut b = correlation.unsafe_get(lag + 1)
    let mut c = correlation.unsafe_get(lag + 2)
    let mut d = correlation.unsafe_get(lag + 3)
    for i = order_limit; i < n; i = i + 1 {
      let value = signal.unsafe_get(i)
      a += value * signal.unsafe_get(i - lag)
      b += value * signal.unsafe_get(i - lag - 1)
      c += value * signal.unsafe_get(i - lag - 2)
      d += value * signal.unsafe_get(i - lag - 3)
    }
    correlation.unsafe_set(lag, a)
    correlation.unsafe_set(lag + 1, b)
    correlation.unsafe_set(lag + 2, c)
    correlation.unsafe_set(lag + 3, d)
    lag += 4
  }
  while lag <= order_limit {
    let mut value = correlation.unsafe_get(lag)
    for i = order_limit; i < n; i = i + 1 {
      value += signal.unsafe_get(i) * signal.unsafe_get(i - lag)
    }
    correlation.unsafe_set(lag, value)
    lag += 1
  }
'''
    prefix_start = original.index('  let correlation = FixedArray::make(order_limit + 1, 0.0)')
    helper = '''///|
// Each lag preserves its scalar reduction order; distinct lags are independent.
fn encoder_lpc_correlations(
  signal : FixedArray[Double],
  order_limit : Int,
) -> FixedArray[Double] {
  let n = signal.length()
'''+original[prefix_start:start]+replacement+'''  correlation
}
'''
    modified = original[:prefix_start] + '  let correlation = encoder_lpc_correlations(signal, order_limit)\n' + original[end:]
    modified += '\n'+helper
    path.write_text(modified, encoding='utf8')
    fn_start = original.index('fn encoder_lpc_models(')
    fn_end = original.index('\n///|', fn_start)
    reference = original[fn_start:fn_end].replace(
        'fn encoder_lpc_models(', 'fn correlation_groups_original_models(', 1)
    test = '''// Frozen C24 model generation preserves the original interleaved correlation.

///|
'''+reference+'''

///|
fn correlation_groups_compare(samples : Array[Int64], order : Int) -> Unit raise {
  let before_variances : Array[Double?] = []
  let after_variances : Array[Double?] = []
  let before = correlation_groups_original_models(samples, order, variances=Some(before_variances))
  let after = encoder_lpc_models(samples, order, variances=Some(after_variances))
  let plain_before = correlation_groups_original_models(samples, order)
  let plain_after = encoder_lpc_models(samples, order)
  assert_eq(plain_after.length(), plain_before.length())
  for i = 0; i < plain_before.length(); i = i + 1 {
    assert_eq(plain_after[i].coefficients, plain_before[i].coefficients)
    assert_eq(plain_after[i].shift, plain_before[i].shift)
    assert_eq(plain_after[i].precision, plain_before[i].precision)
  }
  assert_eq(after.length(), before.length())
  assert_eq(after_variances.length(), before_variances.length())
  for i = 0; i < before.length(); i = i + 1 {
    assert_eq(after[i].coefficients, before[i].coefficients)
    assert_eq(after[i].shift, before[i].shift)
    assert_eq(after[i].precision, before[i].precision)
    match (before_variances[i], after_variances[i]) {
      (None, None) => ()
      (Some(a), Some(b)) => assert_eq(a.reinterpret_as_uint64(), b.reinterpret_as_uint64())
      _ => fail("variance eligibility changed")
    }
  }
}

///|
test "correlation groups preserve model and variance bits across lag tails" {
  for size in [0, 1, 2, 3, 4, 5, 7, 8, 17, 33, 65, 257] {
    for order = 0; order <= 33; order = order + 1 {
      let samples = Array::makei(size, i => ((i * 997 + i * i * 17) % 65536 - 32768).to_int64())
      correlation_groups_compare(samples, order)
    }
  }
}

///|
test "correlation groups preserve long wide and degenerate analysis" {
  for size in [4096, 65535] {
    for variant = 0; variant < 4; variant = variant + 1 {
      let samples = Array::makei(size, i => {
        match variant {
          0 => 0L
          1 => 4294967295L
          2 => (i % 19 - 9).to_int64() * 268435456L
          _ => ((i.to_int64() * 1103515245L + 12345L) & 0xffffffffL) - 2147483648L
        }
      })
      correlation_groups_compare(samples, 32)
    }
  }
}

///|
test "correlation groups raw bits match independent lag outer reduction" {
  for size in [1, 2, 3, 4, 5, 8, 17, 33, 65, 257, 4096, 65535] {
    let maximum = if size > 32 { 32 } else { size - 1 }
    for limit = 0; limit <= maximum; limit = limit + 1 {
      // Tiny alternating terms exercise cancellation independently of whether
      // model analysis later yields a quantized candidate or a usable variance.
      let signal = FixedArray::makei(size, i => {
        if i % 5 == 0 { 0.0 } else if i % 5 == 1 { -0.0 } else {
          (i % 19 - 9).to_double() / (if i % 3 == 0 { 1048576.0 } else { 16.0 })
        }
      })
      let actual = encoder_lpc_correlations(signal, limit)
      for lag = 0; lag <= limit; lag = lag + 1 {
        let mut expected = 0.0
        for i = lag; i < size; i = i + 1 {
          expected += signal[i] * signal[i - lag]
        }
        assert_eq(actual[lag].reinterpret_as_uint64(), expected.reinterpret_as_uint64())
      }
    }
  }
}
'''
    (destination / 'encoder_correlation_groups_wbtest.mbt').write_text(test, encoding='utf8')
    evidence = destination / 'evidence/correlation-groups'
    evidence.mkdir(parents=True)
    (evidence / 'encoder_lpc.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), modified.splitlines(True), fromfile='C24', tofile='C28')), encoding='utf8')
    (evidence / 'README.md').write_text(
        'C28 source-only experiment: original C24 already uses AVX2 across lag lanes. '
        'This experiment instead retains four independent scalar accumulators through the sample loop, '
        'aiming to remove per-sample correlation-array loads/stores. No speed or SIMD result is claimed.\n\n'
        'For each lag, prefix iterations are unchanged; the main loop starts at order_limit and '
        'visits each i in the same ascending order. The initial accumulator bits, product operands '
        'and multiply-then-add ordering are identical. Different lags are independent. No FMA, '
        'reassociation or compiler flag change is requested. For every read, 0 <= lag <= order_limit '
        '<= i < n proves 0 <= i-lag < n. Group tails use the original scalar operation. '
        'Window construction, quantization, variances, model order and shortlisting are unchanged.\n\n'
        'Tests freeze the complete original C24 model generator and compare quantized models and '
        'variance Double bit patterns with and without variance collection, including all lag tails, '
        'tiny inputs, zero/constant signals, 33-bit side-channel values and maximum FLAC block length. '
        'A separate lag-outer scalar oracle directly checks every raw correlation bit pattern, '
        'including signed zeros and cancellation, even when model selection would return no models. '
        'The production correlation helper is the function under test. Builds/tests/timing pending.\n', encoding='utf8')
    files = {str(p.relative_to(destination)): sha(p) for p in destination.rglob('*')
             if p.is_file() and not any(part in {'.mooncakes', '_build'}
                                       for part in p.relative_to(destination).parts)}
    report = dict(status='source_prepared_not_formatted_or_tested', source=str(destination.relative_to(ROOT)),
                  parent=dict(path=str(identity_path.relative_to(ROOT)), sha256=sha(identity_path)),
                  generator_sha256=sha(Path(__file__)), files=files)
    target = ROOT / 'validation/evidence/faster-than-libflac-candidate28-correlation-groups-refined-prepared.json'
    assert not target.exists()
    target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(target)


if __name__ == '__main__':
    main()
