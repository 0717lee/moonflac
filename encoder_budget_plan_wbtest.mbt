///|
test "budget planner retains exhaustive partitions and strict candidate ties" {
  let scratch = EncoderPlanScratch::new()
  let mut state = 29092917U
  for trial = 0; trial < 160; trial = trial + 1 {
    let size = if trial % 5 == 0 { 257 } else { 1 << (4 + trial % 9) }
    let predictor = trial % (if size < 33 { size } else { 33 })
    let samples = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      if i < predictor {
        -2147483648L
      } else if trial % 4 == 0 {
        if i % 113 == 0 {
          2147483647L
        } else {
          (i % 5 - 2).to_int64()
        }
      } else if trial % 4 == 1 {
        -1L
      } else {
        state.reinterpret_as_int().to_int64() >> ((i / 11 + trial) % 32)
      }
    })
    let expected = encoder_residual_plan(samples, predictor, 15)
    match
      encoder_budget_residual_plan(
        samples,
        predictor,
        expected.bits + 1L,
        scratch,
      ) {
      Some(actual) => plan_oracle_equal(actual, expected)
      None => fail("strictly better plan rejected")
    }
    assert_true(
      encoder_budget_residual_plan(samples, predictor, expected.bits, scratch)
      is None,
    )
    assert_true(
      encoder_budget_residual_plan(
        samples,
        predictor,
        expected.bits - 1L,
        scratch,
      )
      is None,
    )
    if size <= 64 {
      plan_oracle_equal(expected, plan_oracle(samples, predictor, 15))
    }
  }
}

///|
test "budget planner scratch cannot mutate retained plans" {
  let scratch = EncoderPlanScratch::new()
  for size in [16, 512, 4096, 32768, 65535] {
    let samples = Array::makei(size, i => {
      if i % 113 == 0 {
        -2147483648L
      } else {
        (i % 5 - 2).to_int64()
      }
    })
    let expected = encoder_residual_plan(samples, 0, 15)
    let actual = encoder_budget_residual_plan(
      samples, 0, 9223372036854775807L, scratch,
    ).unwrap()
    plan_oracle_equal(actual, expected)
    let _ = encoder_budget_residual_plan(Array::make(17, 0L), 1, 100L, scratch)
    plan_oracle_equal(actual, expected)
  }
}

///|
test "budget planner Rice parameter window endpoints and escapes" {
  let scratch = EncoderPlanScratch::new()
  for
    samples in [
      [1L, 1L],
      [-1L, -1L, -2L],
      [0L, 0L, 0L, 0L, 0L, 0L],
      [-2147483648L, 2147483647L, 0L, -1L],
      [32767L, -32768L, 16384L, -16385L],
    ] {
    for predictor = 0; predictor < samples.length(); predictor = predictor + 1 {
      let expected = plan_oracle(samples, predictor, 15)
      let actual = encoder_budget_residual_plan(
        samples,
        predictor,
        expected.bits + 1L,
        scratch,
      ).unwrap()
      plan_oracle_equal(actual, expected)
    }
  }
}
