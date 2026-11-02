///|
test "prefix ready guard preserves independent plans with stale caches and extreme windows" {
  let scratch = EncoderPlanScratch::new()
  let mut state = 409639U
  for trial = 0; trial < 96; trial = trial + 1 {
    let sizes = [16, 32, 64, 96, 128, 256, 512, 1024]
    let size = sizes[trial % sizes.length()]
    let predictor = trial / sizes.length() % (if size < 33 { size } else { 33 })
    let samples = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      if i < predictor {
        1099511627775L
      } else {
        match trial % 6 {
          0 => (i % 3 - 1).to_int64()
          1 => if i % 2 == 0 { 32767L } else { -32768L }
          2 => if i % 2 == 0 { 2147483647L } else { -2147483648L }
          3 => if i / 8 % 2 == 0 { 0L } else { 1048575L }
          _ => state.reinterpret_as_int().to_int64() >> (i % 17)
        }
      }
    })
    let expected = plan_oracle(samples, predictor, 15)
    for budget in [expected.bits, expected.bits + 1L, 9223372036854775807L] {
      // Stale ready flags and wrong prefix values must never survive the
      // new-candidate reset, even when window0/14/clipped30 is involved.
      for k = 0; k < 31; k = k + 1 {
        scratch.ready[k] = (k + trial) % 3 != 0
        scratch.prefixes[k] = Array::make(size + 1, 1234567L)
      }
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

///|
test "prefix ready mixed-column helper contract covers zero fourteen and clipped thirty" {
  // The production helper stays unchanged. Verify each cache state admitted
  // by the caller guard using exact direct sums, including holes in windows.
  for low in [0, 1, 13, 14, 28, 29, 30] {
    let high = if low + 2 > 30 { 30 } else { low + 2 }
    for mask = 0; mask < 8; mask = mask + 1 {
      let scratch = EncoderPlanScratch::new()
      scratch.folded = Array::makei(64, i => i.to_uint() * 982451653U)
      for k = low; k <= high; k = k + 1 {
        if k > 0 && (mask & (1 << (k - low))) != 0 {
          encoder_prepare_leaf_prefixes(scratch, 64, 8, k, k)
        }
      }
      encoder_prepare_leaf_prefixes(scratch, 64, 8, low, high)
      for k = low; k <= high; k = k + 1 {
        if k > 0 {
          let mut expected = 0L
          for value in scratch.folded {
            expected += (value >> k).to_int64()
          }
          assert_eq(encoder_prefix_quotient(scratch, 0, 8, k), expected)
          assert_true(scratch.ready[k])
        }
      }
      assert_false(scratch.ready[0])
    }
  }
}
