///|
test "unsigned folded storage preserves full residual width and quotient sums" {
  let mut seed = 9639L
  for i in 0..<4096 {
    seed = (seed * 1664525L + 1013904223L) % 4294967296L
    let value = if i == 0 {
      -2147483648L
    } else if i == 1 {
      2147483647L
    } else if i == 2 {
      0L
    } else {
      seed - 2147483648L
    }
    let expected = if value < 0L { -value * 2L - 1L } else { value * 2L }
    let actual = encoder_fold_u32(value)
    assert_eq(actual.to_int64(), expected)
    assert_eq(32 - actual.clz(), encoder_signed_width(value))
    for k in 0..<=30 {
      assert_eq((actual >> k).to_int64(), expected >> k)
    }
  }
}
