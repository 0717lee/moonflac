///|
fn symmetric_variance_frozen(
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
