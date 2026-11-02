///|
fn lpc_allocation_frozen_quantize(
  coefficients : Array[Double],
  precision : Int32,
) -> LpcModel? {
  let bound = 1L << (precision - 1)
  for shift = 15; shift >= 0; shift = shift - 1 {
    let scale = (1L << shift).to_double()
    let quantized : Array[Int64] = []
    let mut error = 0.0
    let mut valid = true
    for coefficient in coefficients {
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
      quantized.push(rounded)
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
fn lpc_allocation_frozen_models(
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
  let n = samples.length()
  let mut window_energy = 0.0
  let signal = FixedArray::makei(n, i => {
    // Half-sample endpoints keep even a two-sample input observable.
    let position = (2.0 * i.to_double() + 1.0) / n.to_double() - 1.0
    if variances is Some(_) {
      window_energy += (1.0 - position * position) * (1.0 - position * position)
    }
    samples[i].to_double() / peak * (1.0 - position * position)
  })
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
  let mut coefficients : Array[Double] = []
  for order in 1..<=order_limit {
    let mut numerator = correlation[order]
    for j in 1..<order {
      numerator -= coefficients[j - 1] * correlation[order - j]
    }
    let reflection = numerator / error
    if reflection.is_nan() || reflection.is_inf() || reflection.abs() >= 1.0 {
      break
    }
    let next = Array::makei(order, j => {
      if j == order - 1 {
        reflection
      } else {
        coefficients[j] - reflection * coefficients[order - j - 2]
      }
    })
    coefficients = next
    for precision in [12, 15] {
      if lpc_allocation_frozen_quantize(coefficients, precision) is Some(model) {
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
