///|
/// Integer predictor candidate. Analysis is approximate; the encoder must
/// validate every exact residual and compare its actual encoded cost.
priv struct LpcModel {
  coefficients : Array[Int64]
  shift : Int32
  precision : Int32
}

///|
/// Quantize with error feedback and a nonnegative legal FLAC shift. Reducing
/// the shift handles a coefficient rounding onto the signed positive bound.
fn encoder_lpc_quantize(
  coefficients : Array[Double],
  precision : Int32,
) -> LpcModel? {
  let bound = 1L << (precision - 1)
  let quantized = Array::make(coefficients.length(), 0L)
  for shift = 15; shift >= 0; shift = shift - 1 {
    let scale = (1L << shift).to_double()
    let mut error = 0.0
    let mut valid = true
    for index = 0; index < coefficients.length(); index = index + 1 {
      let coefficient = coefficients[index]
      let value = coefficient * scale + error
      if value.is_nan() ||
        value.is_inf() ||
        value < -bound.to_double() - 1.0 ||
        value > bound.to_double() {
        valid = false
        break
      }
      // Explicit round-away-from-zero avoids backend-specific halfway rules.
      let rounded = (if value >= 0.0 { value + 0.5 } else { value - 0.5 }).to_int64()
      if rounded < -bound || rounded >= bound {
        valid = false
        break
      }
      quantized[index] = rounded
      error = value - rounded.to_double()
    }
    if valid {
      let mut actual_precision = 1
      for coefficient in quantized {
        while actual_precision < 15 &&
              (
                coefficient < -(1L << (actual_precision - 1)) ||
                coefficient >= 1L << (actual_precision - 1)
              ) {
          actual_precision += 1
        }
      }
      return Some({
        coefficients: quantized,
        shift,
        precision: actual_precision,
      })
    }
  }
  None
}

///|
/// Normalized autocorrelation and Levinson-Durbin produce candidates for
/// orders 1..min(max_order,32,n-1). A Welch window reduces boundary bias.
/// Floating point only chooses candidates: it never determines reconstructed
/// PCM. Zero energy or unstable analysis returns the stable models collected
/// so far; the encoder can select another predictor or verbatim coding.
/// Two bounded quantization budgets (12 and 15 bits) are considered per order,
/// in deterministic order, with identical quantized candidates deduplicated.
fn encoder_lpc_models(
  samples : Array[Int64],
  max_order : Int32,
  variances~ : Array[Double?]? = None,
) -> Array[LpcModel] {
  let models : Array[LpcModel] = []
  if samples.length() < 2 || max_order < 1 {
    return models
  }
  let limit = if max_order > 32 { 32 } else { max_order }
  let order_limit = if limit >= samples.length() {
    samples.length() - 1
  } else {
    limit
  }
  let mut peak = 0.0
  for sample in samples {
    let magnitude = sample.to_double().abs()
    if magnitude > peak {
      peak = magnitude
    }
  }
  if peak == 0.0 {
    return models
  }
  let (signal, window_energy) = encoder_lpc_welch(
    samples,
    peak,
    variances is Some(_),
  )
  let correlation = encoder_lpc_correlations(signal, order_limit)
  let variance_correlation = if variances is Some(_) {
    Array::makei(order_limit + 1, i => correlation[i])
  } else {
    []
  }
  let variance_inputs_valid = if variances is Some(_) {
    encoder_lpc_variance_inputs(
      variance_correlation, order_limit, peak, window_energy,
    )
  } else {
    false
  }
  let mut error = correlation[0]
  if error <= 0.0 || error.is_nan() || error.is_inf() {
    return models
  }
  let coefficients : Array[Double] = []
  for order in 1..<=order_limit {
    let mut numerator = correlation[order]
    for j in 1..<order {
      numerator -= coefficients[j - 1] * correlation[order - j]
    }
    let reflection = numerator / error
    if reflection.is_nan() || reflection.is_inf() || reflection.abs() >= 1.0 {
      break
    }
    // Each pair reads both old values before either store; no updated value
    // enters the opposite coefficient's original multiply/subtract expression.
    let previous = order - 1
    for j = 0; j < previous / 2; j = j + 1 {
      let opposite = previous - 1 - j
      let a = coefficients[j]
      let b = coefficients[opposite]
      coefficients[j] = a - reflection * b
      coefficients[opposite] = b - reflection * a
    }
    if previous % 2 != 0 {
      let middle = previous / 2
      let a = coefficients[middle]
      coefficients[middle] = a - reflection * a
    }
    coefficients.push(reflection)
    for precision = 12; precision <= 15; precision = precision + 3 {
      if encoder_lpc_quantize(coefficients, precision) is Some(model) {
        let duplicate = match models.last() {
          Some(previous) =>
            previous.shift == model.shift &&
            previous.coefficients == model.coefficients
          None => false
        }
        if !duplicate {
          models.push(model)
          if variances is Some(values) {
            values.push(
              if variance_inputs_valid {
                encoder_lpc_variance_triangle(
                  variance_correlation, model, peak, window_energy,
                )
              } else {
                encoder_lpc_variance(
                  variance_correlation, model, peak, window_energy,
                )
              },
            )
          }
        }
      }
    }
    error *= 1.0 - reflection * reflection
    if error <= correlation[0] * 1.0e-14 {
      break
    }
  }
  models
}

///|
/// Mean squared linear residual of the quantized predictor in the existing
/// zero-extended, peak-normalized Welch-window autocorrelation model.
/// r0 - 2 sum(a_j r_j) + sum(a_i a_j r_|i-j|), rescaled by peak^2/sum(w^2).
/// This estimates stationary unwindowed PCM variance, not exact Rice cost or
/// integer-floor prediction error. Cancellation-scale or invalid values are
/// explicitly unrankable; the caller uses the established sampled ranking.
fn encoder_lpc_variance(
  correlation : Array[Double],
  model : LpcModel,
  peak : Double,
  window_energy : Double,
) -> Double? {
  let order = model.coefficients.length()
  let mut bounded = order >= 1 &&
    order <= 32 &&
    correlation.length() > order &&
    model.shift >= 0 &&
    model.shift <= 15 &&
    peak >= 1.0 &&
    peak <= 4294967296.0 &&
    window_energy >= 1.0 &&
    window_energy <= 65535.0
  if bounded {
    for coefficient in model.coefficients {
      if coefficient < -16384L || coefficient > 16383L {
        bounded = false
        break
      }
    }
  }
  if bounded {
    for i = 0; i <= order; i = i + 1 {
      let value = correlation[i].abs()
      if !(value <= 65535.0 && (value == 0.0 || value >= 1.0e-200)) {
        bounded = false
        break
      }
    }
  }
  if !bounded {
    return encoder_lpc_variance_original(
      correlation, model, peak, window_energy,
    )
  }
  encoder_lpc_variance_triangle(correlation, model, peak, window_energy)
}

///|
fn encoder_lpc_variance_triangle(
  correlation : Array[Double],
  model : LpcModel,
  peak : Double,
  window_energy : Double,
) -> Double? {
  let order = model.coefficients.length()
  let scale = (1L << model.shift).to_double()
  let a = model.coefficients.map(c => c.to_double() / scale)
  let coefficient_view = a[:]
  let correlation_view = correlation[:]
  let r0 = correlation_view.unsafe_get(0)
  let mut variance = r0
  let mut magnitude = r0.abs()
  for i in 0..<order {
    let ai = coefficient_view.unsafe_get(i)
    let linear = 2.0 * ai * correlation_view.unsafe_get(i + 1)
    variance -= linear
    magnitude += linear.abs()
    let diagonal = ai * ai * r0
    variance += diagonal
    magnitude += diagonal.abs()
    for j in 0..<i {
      let term = ai *
        coefficient_view.unsafe_get(j) *
        correlation_view.unsafe_get(i - j) *
        2.0
      variance += term
      magnitude += term.abs()
    }
  }
  if variance.is_nan() || variance.is_inf() || variance <= magnitude * 1.0e-12 {
    return None
  }
  let result = variance / window_energy * peak * peak
  if result.is_nan() || result.is_inf() || result <= 0.0 {
    None
  } else {
    Some(result)
  }
}

///|
fn encoder_lpc_variance_inputs(
  correlation : Array[Double],
  order : Int32,
  peak : Double,
  window_energy : Double,
) -> Bool {
  if !(order >= 1 &&
    order <= 32 &&
    correlation.length() > order &&
    peak >= 1.0 &&
    peak <= 4294967296.0 &&
    window_energy >= 1.0 &&
    window_energy <= 65535.0) {
    return false
  }
  for i = 0; i <= order; i = i + 1 {
    let value = correlation[i].abs()
    if !(value <= 65535.0 && (value == 0.0 || value >= 1.0e-200)) {
      return false
    }
  }
  true
}

///|
fn encoder_lpc_variance_original(
  correlation : Array[Double],
  model : LpcModel,
  peak : Double,
  window_energy : Double,
) -> Double? {
  let order = model.coefficients.length()
  if correlation.length() <= order || window_energy <= 0.0 || peak <= 0.0 {
    return None
  }
  let scale = (1L << model.shift).to_double()
  let a = model.coefficients.map(c => c.to_double() / scale)
  let mut variance = correlation[0]
  let mut magnitude = correlation[0].abs()
  for i in 0..<order {
    let linear = 2.0 * a[i] * correlation[i + 1]
    variance -= linear
    magnitude += linear.abs()
    for j in 0..<order {
      let lag = if i > j { i - j } else { j - i }
      let term = a[i] * a[j] * correlation[lag]
      variance += term
      magnitude += term.abs()
    }
  }
  // At most ~1100 additions: a deliberately conservative roundoff band.
  if variance.is_nan() || variance.is_inf() || variance <= magnitude * 1.0e-12 {
    return None
  }
  let result = variance / window_energy * peak * peak
  if result.is_nan() || result.is_inf() || result <= 0.0 {
    None
  } else {
    Some(result)
  }
}

///|
// Each lag preserves its scalar reduction order; distinct lags are independent.
fn encoder_lpc_correlations(
  signal : FixedArray[Double],
  order_limit : Int32,
) -> FixedArray[Double] {
  let n = signal.length()
  let correlation = FixedArray::make(order_limit + 1, 0.0)
  // Interleave independent lag accumulators, preserving ascending i and the
  // multiplication/addition order of every individual scalar reduction.
  // Prefix iterations have fewer valid lags; the main loop has a fixed span.
  for i = 0; i < order_limit; i = i + 1 {
    let value = signal.unsafe_get(i)
    for lag = 0; lag <= i; lag = lag + 1 {
      correlation.unsafe_set(
        lag,
        correlation.unsafe_get(lag) + value * signal.unsafe_get(i - lag),
      )
    }
  }
  // Keep the existing interleaved loop when fewer than sixteen lags
  // are available, rather than turning all short-order work into tails.
  if order_limit < 15 || n > 65535 {
    for i = order_limit; i < n; i = i + 1 {
      let value = signal.unsafe_get(i)
      for lag = 0; lag <= order_limit; lag = lag + 1 {
        correlation.unsafe_set(
          lag,
          correlation.unsafe_get(lag) + value * signal.unsafe_get(i - lag),
        )
      }
    }
    return correlation
  }
  // Preserve sixteen independent reduction chains to expose more
  // instruction-level parallelism; each lag retains ascending i.
  let mut lag = 0
  while lag + 15 <= order_limit {
    let mut c0 = correlation.unsafe_get(lag + 0)
    let mut c1 = correlation.unsafe_get(lag + 1)
    let mut c2 = correlation.unsafe_get(lag + 2)
    let mut c3 = correlation.unsafe_get(lag + 3)
    let mut c4 = correlation.unsafe_get(lag + 4)
    let mut c5 = correlation.unsafe_get(lag + 5)
    let mut c6 = correlation.unsafe_get(lag + 6)
    let mut c7 = correlation.unsafe_get(lag + 7)
    let mut c8 = correlation.unsafe_get(lag + 8)
    let mut c9 = correlation.unsafe_get(lag + 9)
    let mut c10 = correlation.unsafe_get(lag + 10)
    let mut c11 = correlation.unsafe_get(lag + 11)
    let mut c12 = correlation.unsafe_get(lag + 12)
    let mut c13 = correlation.unsafe_get(lag + 13)
    let mut c14 = correlation.unsafe_get(lag + 14)
    let mut c15 = correlation.unsafe_get(lag + 15)
    for i = order_limit; i < n; i = i + 1 {
      let value = signal.unsafe_get(i)
      // n<=65535 and i>=order_limit>=lag+15 prove this mask is identity.
      let base = (i - lag - 15) & 0xffff
      c0 += value * signal.unsafe_get(base + 15)
      c1 += value * signal.unsafe_get(base + 14)
      c2 += value * signal.unsafe_get(base + 13)
      c3 += value * signal.unsafe_get(base + 12)
      c4 += value * signal.unsafe_get(base + 11)
      c5 += value * signal.unsafe_get(base + 10)
      c6 += value * signal.unsafe_get(base + 9)
      c7 += value * signal.unsafe_get(base + 8)
      c8 += value * signal.unsafe_get(base + 7)
      c9 += value * signal.unsafe_get(base + 6)
      c10 += value * signal.unsafe_get(base + 5)
      c11 += value * signal.unsafe_get(base + 4)
      c12 += value * signal.unsafe_get(base + 3)
      c13 += value * signal.unsafe_get(base + 2)
      c14 += value * signal.unsafe_get(base + 1)
      c15 += value * signal.unsafe_get(base + 0)
    }
    correlation.unsafe_set(lag + 0, c0)
    correlation.unsafe_set(lag + 1, c1)
    correlation.unsafe_set(lag + 2, c2)
    correlation.unsafe_set(lag + 3, c3)
    correlation.unsafe_set(lag + 4, c4)
    correlation.unsafe_set(lag + 5, c5)
    correlation.unsafe_set(lag + 6, c6)
    correlation.unsafe_set(lag + 7, c7)
    correlation.unsafe_set(lag + 8, c8)
    correlation.unsafe_set(lag + 9, c9)
    correlation.unsafe_set(lag + 10, c10)
    correlation.unsafe_set(lag + 11, c11)
    correlation.unsafe_set(lag + 12, c12)
    correlation.unsafe_set(lag + 13, c13)
    correlation.unsafe_set(lag + 14, c14)
    correlation.unsafe_set(lag + 15, c15)
    lag += 16
  }
  while lag <= order_limit {
    let mut value = correlation.unsafe_get(lag)
    for i = order_limit; i < n; i = i + 1 {
      value += signal.unsafe_get(i) * signal.unsafe_get(i - lag)
    }
    correlation.unsafe_set(lag, value)
    lag += 1
  }
  correlation
}

///|
// Independent sample expressions; energy retains the original ascending sum.
fn encoder_lpc_welch(
  samples : Array[Int64],
  peak : Double,
  with_energy : Bool,
) -> (FixedArray[Double], Double) {
  let n = samples.length()
  let signal = FixedArray::make(n, 0.0)
  let mut window_energy = 0.0
  let mut i = 0
  while i <= n - 4 {
    let p0 = (2.0 * i.to_double() + 1.0) / n.to_double() - 1.0
    let w0 = 1.0 - p0 * p0
    let s0 = samples.unsafe_get(i).to_double() / peak * w0
    let p1 = (2.0 * (i + 1).to_double() + 1.0) / n.to_double() - 1.0
    let w1 = 1.0 - p1 * p1
    let s1 = samples.unsafe_get(i + 1).to_double() / peak * w1
    let p2 = (2.0 * (i + 2).to_double() + 1.0) / n.to_double() - 1.0
    let w2 = 1.0 - p2 * p2
    let s2 = samples.unsafe_get(i + 2).to_double() / peak * w2
    let p3 = (2.0 * (i + 3).to_double() + 1.0) / n.to_double() - 1.0
    let w3 = 1.0 - p3 * p3
    let s3 = samples.unsafe_get(i + 3).to_double() / peak * w3
    if with_energy {
      window_energy += w0 * w0
      window_energy += w1 * w1
      window_energy += w2 * w2
      window_energy += w3 * w3
    }
    signal.unsafe_set(i, s0)
    signal.unsafe_set(i + 1, s1)
    signal.unsafe_set(i + 2, s2)
    signal.unsafe_set(i + 3, s3)
    i += 4
  }
  while i < n {
    let position = (2.0 * i.to_double() + 1.0) / n.to_double() - 1.0
    let weight = 1.0 - position * position
    if with_energy {
      window_energy += weight * weight
    }
    signal.unsafe_set(i, samples.unsafe_get(i).to_double() / peak * weight)
    i += 1
  }
  (signal, window_energy)
}
