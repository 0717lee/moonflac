///|
fn lazy_tree_level_oracle(
  samples : Array[Int64],
  predictor : Int32,
  order : Int32,
) -> Int64 {
  let parts = 1 << order
  let step = samples.length() / parts
  let mut best = 9223372036854775807L
  for rice2 in [false, true] {
    let mut bits = 6L
    let pb = if rice2 { 5 } else { 4 }
    for p = 0; p < parts; p = p + 1 {
      let start = if p == 0 { predictor } else { p * step }
      let end = (p + 1) * step
      let mut width = 0
      for i = start; i < end; i = i + 1 {
        let v = samples[i]
        let mut w = if v == 0L { 0 } else { 1 }
        while w > 0 && (v < -(1L << (w - 1)) || v >= 1L << (w - 1)) {
          w += 1
        }
        if w > width {
          width = w
        }
      }
      let mut cost = 9223372036854775807L
      for k = 0; k <= (if rice2 { 30 } else { 14 }); k = k + 1 {
        let mut candidate = pb.to_int64()
        for i = start; i < end; i = i + 1 {
          let v = samples[i]
          let u = if v < 0L { -(v + 1L) * 2L + 1L } else { 2L * v }
          candidate += (u >> k) + (k + 1).to_int64()
        }
        if candidate < cost {
          cost = candidate
        }
      }
      let escape = (pb + 5 + (end - start) * width).to_int64()
      if width <= 31 && escape < cost {
        cost = escape
      }
      bits += cost
    }
    if bits < best {
      best = bits
    }
  }
  best
}

///|
test "lazy tree universal depth bound is monotone and below scalar level costs" {
  let alphabet = [0L, -1L, 1L, -2L, 2147483647L, -2147483648L]
  for size in [2, 4, 8, 16, 32, 48, 64, 128] {
    for predictor = 0
        predictor < (if size < 33 { size } else { 33 })
        predictor = predictor + 1 {
      for pattern = 0; pattern < 5; pattern = pattern + 1 {
        let samples = Array::makei(size, i => {
          if i < predictor {
            1099511627775L
          } else {
            alphabet[(i * (pattern + 1) + pattern) % alphabet.length()]
          }
        })
        let mut widths = 0L
        for i = predictor; i < size; i = i + 1 {
          let v = samples[i]
          let mut w = if v == 0L { 0 } else { 1 }
          while w > 0 && (v < -(1L << (w - 1)) || v >= 1L << (w - 1)) {
            w += 1
          }
          widths += w.to_int64()
        }
        let mut previous = 0L
        for order = 0; order <= 7; order = order + 1 {
          if size % (1 << order) == 0 && size >> order > predictor {
            let bound = encoder_depth_lower_bound(
              size, predictor, order, widths,
            )
            assert_true(bound > previous)
            assert_true(
              bound <= lazy_tree_level_oracle(samples, predictor, order),
            )
            previous = bound
          }
        }
      }
    }
  }
}

///|
test "lazy tree preserves deep winners and scratch reuse across trimmed depths" {
  let scratch = EncoderPlanScratch::new()
  let deep = Array::makei(8192, i => {
    if i / 4 % 2 == 0 {
      0L
    } else {
      2147483647L
    }
  })
  let expected = plan_oracle(deep, 0, 15)
  assert_true(expected.order > 8)
  for budget in [expected.bits, expected.bits + 1L, 9223372036854775807L] {
    match encoder_budget_residual_plan(deep, 0, budget, scratch) {
      Some(actual) => {
        assert_true(expected.bits < budget)
        plan_oracle_equal(actual, expected)
      }
      None => assert_true(expected.bits >= budget)
    }
  }
  for size in [4096, 96, 1, 257, 1024, 65535] {
    let samples = Array::makei(size, i => (i % 5 - 2).to_int64())
    let predictor = if size > 32 { 31 } else { 0 }
    let expected = plan_oracle(samples, predictor, 15)
    for budget in [6L, expected.bits - 1L, expected.bits, expected.bits + 1L] {
      match encoder_budget_residual_plan(samples, predictor, budget, scratch) {
        Some(actual) => {
          assert_true(expected.bits < budget)
          plan_oracle_equal(actual, expected)
        }
        None => assert_true(expected.bits >= budget)
      }
    }
  }
}
