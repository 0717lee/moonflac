///|
test "encoder borrowed input validation is atomic and does not retain its view" {
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 1, bits_per_sample: 4, },
    block_size=16,
    effort=0,
  )
  let encoder = Encoder::new(config)
  ignore(encoder.next())
  let input = [100, 1, 2, 3, 100]
  assert_eq(encoder.push_view(input[1:4]), 3)
  input.fill(100)
  assert_eq(encoder.pcm, [1, 2, 3])
  let rejected = try {
    ignore(encoder.push_view([4, 5, 8][:]))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
  assert_eq(encoder.pcm, [1, 2, 3])
  let terminal = try {
    ignore(encoder.push_view([0][:]))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(terminal)
}
