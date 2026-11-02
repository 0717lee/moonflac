///|
test "adaptive partition bound confirmed dense background needs order ten" {
  // Independent review seed202609291339, tail-4096-255, channel1,
  // fixed predictor0. Preserve the pulse signs explicitly, without TEMP input.
  let signs = [
    -1, 1, 1, 1, 1, -1, 1, 1, 1, -1, 1, 1, -1, 1, 1, 1, -1, -1, -1, -1, -1, -1, 1,
    -1, -1, 1, -1, 1, -1, 1, -1, -1, -1, -1, 1, 1,
  ]
  let samples = Array::makei(4096, i => {
    if (i + 19) % 113 == 0 {
      if signs[(i - 94) / 113] < 0 {
        -16777216L
      } else {
        16777215L
      }
    } else {
      ((i + 1) % 5 - 2).to_int64()
    }
  })
  let expected = plan_oracle(samples, 0, 15)
  assert_eq(expected.order, 10)
  // Review subframe totals include an additional 8-bit subframe header.
  assert_eq(expected.bits, 18947L)
  let coarse = encoder_residual_plan(samples, 0, 8)
  assert_eq(coarse.bits, 24353L)
  plan_oracle_equal(encoder_adaptive_residual_plan(samples, 0), expected)
}

///|
test "partition lower bound matches independent scalar partition sum" {
  for size in [32, 256, 512, 1024] {
    for predictor in [0, 1, 4, 15] {
      let widths = Array::makei(size, i => {
        if i < predictor {
          32
        } else if i % 29 == 0 {
          32
        } else {
          i % 6
        }
      })
      for order = 0; order <= 10; order = order + 1 {
        if size % (1 << order) != 0 || size >> order <= predictor {
          continue
        }
        let length = size >> order
        let mut expected = 6L
        for p = 0; p < 1 << order; p = p + 1 {
          let start = if p == 0 { predictor } else { p * length }
          let end = (p + 1) * length
          let mut rice = 4L
          let mut maximum = 0
          for i = start; i < end; i = i + 1 {
            rice += (widths[i] + 1).to_int64()
            if widths[i] > maximum {
              maximum = widths[i]
            }
          }
          let escape = 9L + (end - start).to_int64() * maximum.to_int64()
          expected += if maximum <= 31 && escape < rice { escape } else { rice }
        }
        assert_eq(
          encoder_partition_lower_bound(widths, predictor, order),
          expected,
        )
      }
    }
  }
}

///|
test "adaptive partition bound equals exhaustive plans with nonzero pulse backgrounds" {
  let workspace : Array[Array[Int64]] = []
  for size in [16, 255, 256, 257, 512, 1024, 4096, 32768] {
    for background in [-3L, -1L, 0L, 1L, 3L] {
      for predictor in [0, 1, 4, 15] {
        let samples = Array::makei(size, i => {
          if i < predictor {
            2147483647L
          } else if (i + 17) % 251 == 0 {
            if i % 2 == 0 {
              1073741823L
            } else {
              -1073741824L
            }
          } else {
            background
          }
        })
        let expected = encoder_residual_plan(samples, predictor, 15)
        let actual = encoder_adaptive_residual_plan(
          samples,
          predictor,
          workspace~,
        )
        plan_oracle_equal(actual, expected)
        // Refinement uses scratch twice; later calls must preserve returned plans.
        let tiny = Array::make(16, 0L)
        let _ = encoder_adaptive_residual_plan(tiny, 0, workspace~)
        plan_oracle_equal(actual, expected)
      }
    }
  }
}

///|
test "adaptive partition bound randomized widths warmups and method boundaries" {
  let workspace : Array[Array[Int64]] = []
  let mut state = 29099639U
  for trial = 0; trial < 160; trial = trial + 1 {
    let size = if trial % 5 == 0 { 257 } else { 1 << (4 + trial % 9) }
    let predictor = trial % (if size < 33 { size } else { 33 })
    let samples = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      if i < predictor {
        -2147483648L
      } else if trial % 4 == 0 {
        let edges = [
          -2147483648L, -1073741825L, -1073741824L, -1L, 0L, 1L, 1073741823L, 1073741824L,
          2147483647L,
        ]
        edges[i % edges.length()]
      } else {
        state.reinterpret_as_int().to_int64() >> ((i / 11 + trial) % 32)
      }
    })
    plan_oracle_equal(
      encoder_adaptive_residual_plan(samples, predictor, workspace~),
      encoder_residual_plan(samples, predictor, 15),
    )
    // Small cases additionally compare against the scalar all-k/all-order oracle.
    if size <= 64 {
      plan_oracle_equal(
        encoder_adaptive_residual_plan(samples, predictor, workspace~),
        plan_oracle(samples, predictor, 15),
      )
    }
  }
}
