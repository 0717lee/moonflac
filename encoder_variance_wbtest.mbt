///|
test "analytical quantized LPC quadratic form and normalization" {
  let model : LpcModel = { coefficients: [1L, 1L], shift: 1, precision: 2, }
  assert_eq(encoder_lpc_variance([5.0, 2.0, 1.0], model, 2.0, 4.0), Some(5.5))
  assert_eq(encoder_lpc_variance([5.0, 2.0, 1.0], model, 4.0, 4.0), Some(22.0))
  let perfect : LpcModel = { coefficients: [1L], shift: 0, precision: 2, }
  assert_eq(encoder_lpc_variance([1.0, 1.0], perfect, 1.0, 1.0), None)
  assert_eq(encoder_lpc_variance([1.0, 2.0], perfect, 1.0, 1.0), None)
  assert_eq(encoder_lpc_variance([1.0, 0.0], perfect, 1.0, 0.0), None)
}

///|
test "analytical variance log2 bounded approximation" {
  for
    pair in [
      (0.25, -2.0),
      (1.0, 0.0),
      (2.0, 1.0),
      (8.0, 3.0),
      (1.5, 0.5849625007211562),
    ] {
    let (value, expected) = pair
    assert_true((encoder_variance_log2(value) - expected).abs() < 0.00000016)
  }
}

///|
test "analytical model collection preserves every quantized candidate" {
  let samples = Array::makei(512, i => (i * 37 % 997 - 499).to_int64())
  let original = encoder_lpc_models(samples, 32)
  let variances : Array[Double?] = []
  let analyzed = encoder_lpc_models(samples, 32, variances=Some(variances))
  assert_true(original.length() > 0)
  assert_eq(original.length(), analyzed.length())
  assert_eq(variances.length(), analyzed.length())
  for i in 0..<original.length() {
    assert_eq(original[i].coefficients, analyzed[i].coefficients)
    assert_eq(original[i].shift, analyzed[i].shift)
    assert_eq(original[i].precision, analyzed[i].precision)
  }
}

///|
test "analytical ranking ties stable and invalid variance uses prior pool ranking" {
  let samples = Array::makei(512, i => (i % 7 - 3).to_int64())
  let models : Array[LpcModel] = [
    { coefficients: [1L], shift: 0, precision: 3, },
    { coefficients: [2L], shift: 0, precision: 3, },
  ]
  let ranked = encoder_lpc_variance_ranking(
    samples,
    models,
    [Some(4.0), Some(4.0)],
    16,
  )
  assert_eq(ranked[0].coefficients, models[0].coefficients)
  assert_eq(ranked[1].coefficients, models[1].coefficients)
  for
    values in [
      [None, Some(4.0)],
      [Some(-1.0), Some(4.0)],
      [Some(0.0), Some(4.0)],
    ] {
    let fallback = encoder_lpc_variance_ranking(samples, models, values, 16)
    let prior = encoder_lpc_shortlist(
      samples,
      models,
      16,
      limit=models.length(),
    )
    assert_eq(fallback.map(m => m.coefficients), prior.map(m => m.coefficients))
  }
}

///|
test "one PCM quantum variance guard boundary and whole pool fallback" {
  let samples = Array::make(512, 0L)
  let models : Array[LpcModel] = [
    { coefficients: [1L], shift: 0, precision: 3, },
    { coefficients: [2L], shift: 0, precision: 3, },
  ]
  let prior = encoder_lpc_shortlist(samples, models, 16, limit=models.length())
  assert_eq(prior[0].coefficients, models[0].coefficients)
  let boundary = encoder_lpc_variance_ranking(
    samples,
    models,
    [Some(4.0), Some(1.0)],
    16,
  )
  assert_eq(boundary[0].coefficients, models[1].coefficients)
  let below = encoder_lpc_variance_ranking(
    samples,
    models,
    [Some(4.0), Some(0.999999999999)],
    16,
  )
  assert_eq(below.map(m => m.coefficients), prior.map(m => m.coefficients))
  let low_first = encoder_lpc_variance_ranking(
    samples,
    models,
    [Some(0.25), Some(4.0)],
    16,
  )
  assert_eq(low_first.map(m => m.coefficients), prior.map(m => m.coefficients))
}
