///|
test "LPC quantization keeps legal coefficients shifts and exact predictions" {
  let coefficients = [1.98, -0.99]
  for precision in [12, 15] {
    let model = encoder_lpc_quantize(coefficients, precision).unwrap()
    assert_true(model.shift >= 0 && model.shift <= 15)
    assert_true(model.precision >= 1 && model.precision <= 15)
    let bound = 1L << (model.precision - 1)
    for coefficient in model.coefficients {
      assert_true(coefficient >= -bound && coefficient < bound)
    }
    let reconstructed = model.coefficients[0].to_double() /
      (1L << model.shift).to_double()
    assert_true((reconstructed - 1.98).abs() < 0.002)
    let prediction = (
        model.coefficients[0] * 4294967295L +
        model.coefficients[1] * -4294967295L
      ) >>
      model.shift
    assert_true(prediction > 12000000000L && prediction < 14000000000L)
  }
}

///|
test "LPC order two predicts a known integer oscillator" {
  let samples : Array[Int64] = [0L, 1000000L]
  for i in 2..<2048 {
    samples.push(((127L * samples[i - 1]) >> 6) - samples[i - 2])
  }
  let models = encoder_lpc_models(samples, 2)
  let mut best = 1.0e30
  let mut original = 0.0
  for i in 2..<samples.length() {
    original += samples[i].to_double() * samples[i].to_double()
  }
  for model in models {
    if model.coefficients.length() != 2 {
      continue
    }
    let mut residual_energy = 0.0
    for i in 2..<samples.length() {
      let prediction = (
          model.coefficients[0] * samples[i - 1] +
          model.coefficients[1] * samples[i - 2]
        ) >>
        model.shift
      let residual = (samples[i] - prediction).to_double()
      residual_energy += residual * residual
    }
    if residual_energy < best {
      best = residual_energy
    }
  }
  assert_true(best < original / 10000.0)
}

///|
test "LPC considers all 32 orders with wide 33-bit inputs deterministically" {
  let mut state = 13U
  let samples = Array::makei(1024, _ => {
    state = state * 1664525U + 1013904223U
    state.to_int64() * 2L - 4294967295L
  })
  let models = encoder_lpc_models(samples, 32)
  let again = encoder_lpc_models(samples, 32)
  assert_eq(models.length(), again.length())
  for order in 1..<=32 {
    assert_true(models.any(model => model.coefficients.length() == order))
  }
  assert_true(models.length() <= 64)
  for i in 0..<models.length() {
    let model = models[i]
    assert_eq(model.coefficients, again[i].coefficients)
    assert_eq(model.shift, again[i].shift)
    let bound = 1L << (model.precision - 1)
    for coefficient in model.coefficients {
      assert_true(coefficient >= -bound && coefficient < bound)
    }
    // Even a full 32-tap legal predictor on 33-bit samples fits signed Int64.
    assert_true(
      model.coefficients.length().to_int64() * (bound - 1L) * 4294967295L <
      9223372036854775807L,
    )
  }
  assert_eq(encoder_lpc_models(Array::make(128, 0L), 32).length(), 0)
  assert_eq(encoder_lpc_models([1L], 32).length(), 0)
}
