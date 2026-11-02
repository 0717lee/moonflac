///|
fn c76_compare(
  samples : Array[Int64],
  predictor : Int32,
  budget : Int64,
  actual_scratch : EncoderPlanScratch,
  reference_scratch : EncoderPlanScratch,
) -> Unit raise {
  // Both planners must begin with equivalent prior contents and capacities.
  assert_eq(actual_scratch.folded, reference_scratch.folded)
  assert_eq(actual_scratch.widths, reference_scratch.widths)
  assert_eq(actual_scratch.width_sums, reference_scratch.width_sums)
  assert_eq(actual_scratch.sums, reference_scratch.sums)
  assert_eq(actual_scratch.ready, reference_scratch.ready)
  assert_eq(actual_scratch.prefixes, reference_scratch.prefixes)
  let input_copy = samples.copy()
  let expected = c76_checked_residual_plan(
    samples, predictor, budget, reference_scratch,
  )
  let actual = encoder_budget_residual_plan(
    samples, predictor, budget, actual_scratch,
  )
  assert_eq(samples, input_copy)
  assert_eq(actual_scratch.folded, reference_scratch.folded)
  assert_eq(actual_scratch.widths, reference_scratch.widths)
  assert_eq(actual_scratch.width_sums, reference_scratch.width_sums)
  assert_eq(actual_scratch.sums, reference_scratch.sums)
  assert_eq(actual_scratch.ready, reference_scratch.ready)
  match (actual, expected) {
    (Some(a), Some(b)) => plan_oracle_equal(a, b)
    (None, None) => ()
    _ => fail("C76 checked planner presence differs")
  }
}

///|
test "planner views legal sizes predictors and strict budgets" {
  let actual = EncoderPlanScratch::new()
  let reference = EncoderPlanScratch::new()
  for size in [1, 2, 15, 16, 17, 32, 64, 256, 512, 4096, 32768, 65535, 65536] {
    for predictor in [0, 1, 4, 31, 32, size - 1] {
      if predictor < size {
        let samples = Array::makei(size, i => {
          if i < predictor {
            -2147483648L
          } else {
            (i % 17 - 8).to_int64()
          }
        })
        let best = c76_checked_residual_plan(
          samples,
          predictor,
          9223372036854775807L,
          EncoderPlanScratch::new(),
        ).unwrap()
        for
          budget in [
            0L,
            6L,
            7L,
            best.bits - 1L,
            best.bits,
            best.bits + 1L,
            9223372036854775807L,
          ] {
          c76_compare(samples, predictor, budget, actual, reference)
        }
      }
    }
  }
}

///|
test "planner views every folded width and warmup prefixes" {
  let actual = EncoderPlanScratch::new()
  let reference = EncoderPlanScratch::new()
  for width = 0; width <= 32; width = width + 1 {
    let folded = if width == 32 { 4294967295L } else { (1L << width) - 1L }
    let value = if folded % 2L == 0L {
      folded / 2L
    } else {
      -(folded / 2L) - 1L
    }
    for predictor in [0, 1, 4, 31, 32] {
      let samples = Array::makei(1024, i => {
        if i < predictor {
          2147483647L
        } else if i % 3 == 0 {
          0L
        } else {
          value
        }
      })
      let best = c76_checked_residual_plan(
        samples,
        predictor,
        9223372036854775807L,
        EncoderPlanScratch::new(),
      ).unwrap()
      for budget in [best.bits, best.bits + 1L, 9223372036854775807L] {
        c76_compare(samples, predictor, budget, actual, reference)
      }
    }
  }
}

///|
test "planner views coarse fine resize reused scratch ownership" {
  let actual = EncoderPlanScratch::new()
  let reference = EncoderPlanScratch::new()
  c76_compare(Array::make(64, 1L), 4, 9223372036854775807L, actual, reference)
  let samples = Array::makei(32768, i => {
    if i / 32 % 2 == 0 {
      0L
    } else {
      1048576L
    }
  })
  c76_compare(samples, 0, 9223372036854775807L, actual, reference)
  assert_true(actual.widths.length() > 512)
  assert_true(actual.folded.length() >= samples.length())
  let retained = encoder_budget_residual_plan(
    samples, 0, 9223372036854775807L, actual,
  ).unwrap()
  let expected = c76_checked_residual_plan(
    samples, 0, 9223372036854775807L, reference,
  ).unwrap()
  for size in [17, 512, 4096, 65535, 16] {
    let next = Array::makei(size, i => {
      if i % 2 == 0 {
        -2147483648L
      } else {
        2147483647L
      }
    })
    c76_compare(next, 1, 9223372036854775807L, actual, reference)
    c76_compare(next, 0, 7L, actual, reference)
    plan_oracle_equal(retained, expected)
  }
}
