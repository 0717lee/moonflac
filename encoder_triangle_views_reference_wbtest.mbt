///|
fn triangle_views_frozen(
  correlation : Array[Double],
  model : LpcModel,
  peak : Double,
  window_energy : Double,
) -> Double? {
  let order = model.coefficients.length()
  let scale = (1L << model.shift).to_double()
  let a = model.coefficients.map(c => c.to_double() / scale)
  let mut variance = correlation[0]
  let mut magnitude = correlation[0].abs()
  for i in 0..<order {
    let linear = 2.0 * a[i] * correlation[i + 1]
    variance -= linear
    magnitude += linear.abs()
    let diagonal = a[i] * a[i] * correlation[0]
    variance += diagonal
    magnitude += diagonal.abs()
    for j in 0..<i {
      let term = a[i] * a[j] * correlation[i - j] * 2.0
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
