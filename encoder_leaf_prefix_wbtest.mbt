///|
test "leaf prefix fused windows equal independent residual oracle" {
  let scratch = EncoderPlanScratch::new()
  let mut state = 963930U
  for trial = 0; trial < 108; trial = trial + 1 {
    let sizes = [16, 32, 48, 64, 96, 128, 256, 257, 384, 512, 1024, 2048]
    let size = sizes[trial % sizes.length()]
    let predictors = [0, 1, 4, 7, 15, 31]
    let predictor = predictors[trial / sizes.length() % predictors.length()] %
      size
    let samples = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      if i < predictor {
        1099511627775L
      } else if trial % 6 == 0 {
        0L
      } else if trial % 6 == 1 {
        if i % 13 == 0 {
          2147483647L
        } else {
          -1L
        }
      } else if trial % 6 == 2 {
        let edges = [-2147483648L, 2147483647L, -1L, 0L, 1L, 32768L, -32768L]
        edges[i % edges.length()]
      } else {
        state.reinterpret_as_int().to_int64() >> ((i / 17 + trial) % 32)
      }
    })
    let expected = plan_oracle(samples, predictor, 15)
    for
      budget in [
        6L,
        expected.bits - 1L,
        expected.bits,
        expected.bits + 1L,
        9223372036854775807L,
      ] {
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
test "leaf prefix boundaries warmups cached holes and clipped Rice column" {
  for size in [32, 96, 256, 1024] {
    for predictor in [0, 1, 7, 15] {
      let mut maximum = 0
      while size % (1 << (maximum + 1)) == 0 &&
            size >> (maximum + 1) > predictor {
        maximum += 1
      }
      let leaves = 1 << maximum
      let scratch = EncoderPlanScratch::new()
      scratch.folded = Array::makei(size, i => {
        if i < predictor {
          0U
        } else {
          (i.to_int64() * 982451653L % 4294967295L)
          .to_int()
          .reinterpret_as_uint()
        }
      })
      // Prebuilt middle columns exercise both two-column and one-column holes.
      for k in [1, 14, 29] {
        encoder_prepare_leaf_prefixes(scratch, size, leaves, k, k)
      }
      for low in [0, 13, 28] {
        encoder_prepare_leaf_prefixes(scratch, size, leaves, low, low + 2)
        for k = low; k <= low + 2; k = k + 1 {
          if k == 0 {
            assert_false(scratch.ready[0])
            continue
          }
          assert_eq(scratch.prefixes[k].length(), leaves + 1)
          for order = 0; order <= maximum; order = order + 1 {
            let parts = 1 << order
            let step = size >> order
            let leaf_step = leaves >> order
            for p = 0; p < parts; p = p + 1 {
              let mut expected = 0L
              for i = p * step; i < (p + 1) * step; i = i + 1 {
                expected += scratch.folded[i].to_int64() >> k
              }
              assert_eq(
                encoder_prefix_quotient(
                  scratch,
                  p * leaf_step,
                  (p + 1) * leaf_step,
                  k,
                ),
                expected,
              )
            }
          }
        }
      }
      // A ready column must be reused rather than rebuilt from altered input.
      let retained = scratch.prefixes[14].copy()
      scratch.folded.fill(0U)
      encoder_prepare_leaf_prefixes(scratch, size, leaves, 14, 14)
      assert_eq(scratch.prefixes[14], retained)
    }
  }
}
