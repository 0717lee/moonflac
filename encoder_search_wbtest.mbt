///|
test "Rice convex search equals exhaustive costs including ties and escapes" {
  let mut state = 9639U
  for trial = 0; trial < 1000; trial = trial + 1 {
    let count = trial % 65
    let quotients = Array::make(31, 0L)
    let mut width = 0
    for i = 0; i < count; i = i + 1 {
      state = state * 1664525U + 1013904223U
      let value = state.reinterpret_as_int().to_int64() >> (trial % 32)
      let folded = if value < 0L { -value * 2L - 1L } else { value * 2L }
      for k = 0; k <= 30; k = k + 1 {
        quotients[k] += folded >> k
      }
      let mut w = if value == 0L { 0 } else { 1 }
      while w > 0 && (value < -(1L << (w - 1)) || value >= 1L << (w - 1)) {
        w += 1
      }
      assert_eq(encoder_signed_width(value), w)
      if w > width {
        width = w
      }
    }
    let node : EncoderRiceNode = { quotients, count, width, }
    for rice2 in [false, true] {
      let pb = if rice2 { 5 } else { 4 }
      let maximum = if rice2 { 30 } else { 14 }
      let mut parameter = 0
      let mut expected = quotients[0] + count.to_int64() + pb.to_int64()
      for k = 1; k <= maximum; k = k + 1 {
        let bits = quotients[k] +
          (k + 1).to_int64() * count.to_int64() +
          pb.to_int64()
        if bits < expected {
          expected = bits
          parameter = k
        }
      }
      if width <= 31 {
        let escaped = (pb + 5).to_int64() + width.to_int64() * count.to_int64()
        if escaped < expected {
          expected = escaped
          parameter = (1 << pb) - 1
        }
      }
      let (actual, cost) = encoder_partition(node, rice2)
      assert_eq(cost, expected)
      assert_eq(actual.parameter, parameter)
    }
  }
}
