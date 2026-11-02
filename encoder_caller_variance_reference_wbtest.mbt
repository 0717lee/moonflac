///|
fn caller_variance_frozen_models(
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
              encoder_lpc_variance(
                variance_correlation, model, peak, window_energy,
              ),
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
