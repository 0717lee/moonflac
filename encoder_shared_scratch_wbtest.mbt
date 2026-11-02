///|
test "persistent scratch matches fresh frames across sizes formats and effort" {
  let scratch = EncoderPlanScratch::new()
  let saved : Array[Bytes] = []
  let copies : Array[Bytes] = []
  for trial = 0; trial < 27; trial = trial + 1 {
    let sizes = [4096, 17, 256, 1024, 257, 16, 2048, 31, 512]
    let size = sizes[trial % sizes.length()]
    let bits = [4, 16, 24, 32][trial % 4]
    let channels = [1, 2, 8][trial % 3]
    let format : PcmFormat = {
      sample_rate: 48000,
      bits_per_sample: bits,
      channels,
    }
    let bound = 1L << (bits - 1)
    let planes = Array::makei(channels, c => {
      Array::makei(size, i => {
        if trial % 5 == 0 {
          0
        } else {
          ((i.to_int64() * 7919L + c.to_int64() * 104729L) % (bound * 2L) -
          bound).to_int()
        }
      })
    })
    let fresh = encode_frame(format, planes, trial.to_int64(), true, trial % 9)
    let reused = encode_frame_validated(
      format,
      planes,
      trial.to_int64(),
      true,
      trial % 9,
      plan_scratch=scratch,
    )
    assert_eq(reused, fresh)
    saved.push(reused)
    copies.push(Bytes::makei(reused.length(), i => reused[i]))
    for plane in planes {
      plane.fill(0)
    }
    for i = 0; i < saved.length(); i = i + 1 {
      assert_eq(saved[i], copies[i])
    }
  }
}

///|
test "persistent scratch failure prefix and single partition leave no stale data" {
  let scratch = EncoderPlanScratch::new()
  let large = Array::makei(1024, i => (i % 7 - 3).to_int64())
  let first = encoder_subframe(large, 16, 8, plan_scratch=scratch)
  let expected = encoder_subframe(large, 16, 8)
  assert_true(!scratch.predict([0L, 1L, 2L, 3L, 4L], [2147483647L], 0))
  let _ = encoder_budget_residual_plan([1L, 2L, 3L], 1, 6L, scratch)
  let _ = encoder_budget_residual_plan([1L, 2L, 3L], 1, 1000L, scratch)
  let prime = Array::makei(257, i => (i % 3 - 1).to_int64())
  let reused = encoder_subframe(prime, 4, 8, plan_scratch=scratch)
  let fresh = encoder_subframe(prime, 4, 8)
  assert_eq(reused.kind, fresh.kind)
  assert_eq(reused.bits, fresh.bits)
  assert_eq(reused.residual, fresh.residual)
  assert_eq(first.kind, expected.kind)
  assert_eq(first.bits, expected.bits)
  assert_eq(first.residual, expected.residual)
  match (first.plan, expected.plan) {
    (Some(a), Some(b)) => plan_oracle_equal(a, b)
    (None, None) => ()
    _ => fail("plan ownership changed")
  }
}

///|
test "interleaved encoders retain independent reusable planning scratch" {
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 2, bits_per_sample: 16, },
    block_size=256,
    effort=8,
  )
  let a = Encoder::new(config)
  let b = Encoder::new(config)
  let bytes_a : Array[Byte] = []
  let bytes_b : Array[Byte] = []
  let input_a : Array[Int32] = []
  let input_b : Array[Int32] = []
  // Drain headers, then alternate complete blocks between encoder instances.
  for encoder in [a, b] {
    assert_true(encoder.next() is EncodedBytes(_))
  }
  for block = 0; block < 4; block = block + 1 {
    let block_a = Array::makei(512, i => (i * 31 + block * 97) % 32768 - 16384)
    let block_b = Array::makei(512, i => (i * 997 + block * 13) % 65536 - 32768)
    for value in block_a {
      input_a.push(value)
    }
    for value in block_b {
      input_b.push(value)
    }
    assert_eq(a.push(block_a), 512)
    assert_eq(b.push(block_b), 512)
    block_a.fill(0)
    block_b.fill(0)
    for pair in [(a, bytes_a), (b, bytes_b)] {
      let (encoder, bytes) = pair
      match encoder.next() {
        EncodedBytes(chunk) =>
          for byte in chunk {
            bytes.push(byte)
          }
        _ => fail("expected complete frame")
      }
    }
  }
  for pair in [(a, bytes_a, input_a), (b, bytes_b, input_b)] {
    let (encoder, bytes, input) = pair
    encoder.finish()
    let summary = match encoder.next() {
      EncoderDone(summary) => summary
      _ => fail("expected encoder completion")
    }
    let output = Array::makei(summary.final_header.length(), i => {
      summary.final_header[i]
    })
    for byte in bytes {
      output.push(byte)
    }
    assert_eq(Bytes::from_array(output), encode_pcm(input, config))
  }
}
