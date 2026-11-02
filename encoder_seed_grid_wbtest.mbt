///|
fn seed_grid_compare(
  samples : Array[Int64],
  predictor : Int32,
  scratch : EncoderPlanScratch,
) -> EncoderResidual raise {
  // Independent per-partition exhaustive Rice/Rice2/escape oracle.
  let expected = plan_oracle(samples, predictor, 15)
  let actual = encoder_budget_residual_plan(
    samples, predictor, 9223372036854775807L, scratch,
  ).unwrap()
  plan_oracle_equal(actual, expected)
  let tight = encoder_budget_residual_plan(
    samples,
    predictor,
    expected.bits + 1L,
    scratch,
  ).unwrap()
  plan_oracle_equal(tight, expected)
  assert_true(
    encoder_budget_residual_plan(samples, predictor, expected.bits, scratch)
    is None,
  )
  assert_true(
    encoder_budget_residual_plan(samples, predictor, 6L, scratch) is None,
  )
  actual
}

///|
test "order0 seed shrinks loose deep grid before refinement and retains ties" {
  let scratch = EncoderPlanScratch::new()
  let constant = Array::make(8192, 20000L)
  let plan = encoder_budget_residual_plan(
    constant, 0, 9223372036854775807L, scratch,
  ).unwrap()
  plan_oracle_equal(plan, plan_oracle(constant, 0, 15))
  assert_eq(plan.order, 0)
  // Initial order8 statistics only; seed rules out every higher order.
  assert_eq(scratch.widths.length(), 512)
  for prefix in scratch.prefixes {
    assert_eq(prefix.length(), 0)
  }
  let almost = Array::makei(8192, i => if i < 100 { 0L } else { 20000L })
  let actual = seed_grid_compare(almost, 0, scratch)
  assert_true(actual.order <= 8)
  assert_eq(scratch.widths.length(), 512)
  for prefix in scratch.prefixes {
    assert_true(prefix.length() <= 257)
  }
}

///|
test "order0 seed keeps strict deep winners and reusable capacity bound" {
  let scratch = EncoderPlanScratch::new()
  let alternating = Array::makei(8192, i => {
    if i / 8 % 2 == 0 {
      0L
    } else {
      20000L
    }
  })
  let deep = seed_grid_compare(alternating, 0, scratch)
  assert_true(deep.order > 8)
  assert_true(scratch.widths.length() > 512)
  let retained = scratch.widths.length()
  let saved = deep.bits
  let _ = seed_grid_compare(Array::make(8192, 20000L), 0, scratch)
  assert_eq(scratch.widths.length(), retained)
  assert_eq(deep.bits, saved)
  assert_true(scratch.widths.length() <= 65536)
  assert_true(scratch.folded.length() <= 65535)
  for prefix in scratch.prefixes {
    assert_true(prefix.length() <= 32769)
  }
  // The maximum0 wrapper and non-refining path remain identical.
  let _ = seed_grid_compare(
    [0L, 3L, -2L, 2147483647L, -2147483647L],
    1,
    scratch,
  )
  let _ = seed_grid_compare(
    Array::makei(256, i => (i % 17 - 8).to_int64()),
    4,
    scratch,
  )
}
