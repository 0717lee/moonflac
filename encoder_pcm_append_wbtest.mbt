///|
fn c80_encoder(block : Int32) -> Encoder raise {
  Encoder::new(
    EncoderConfig::new(
      { sample_rate: 48000, channels: 2, bits_per_sample: 4, },
      block_size=block,
      effort=0,
    ),
  )
}

///|
fn c80_state(a : Encoder, b : Encoder) -> Unit raise {
  assert_eq(a.pcm, b.pcm)
  assert_eq(a.peak_pcm, b.peak_pcm)
  assert_eq(a.ended, b.ended)
  assert_eq(a.samples, b.samples)
  assert_eq(a.frames, b.frames)
  assert_eq(a.queued, b.queued)
  match (a.failed, b.failed) {
    (None, None) => ()
    (Some(x), Some(y)) => assert_eq(x.to_string(), y.to_string())
    _ => assert_true(false)
  }
  assert_true(a.pcm.length() <= a.config.block_size * 2)
}

///|
fn c80_push(a : Encoder, b : Encoder, view : ArrayView[Int32]) -> Int32 raise {
  let x = a.push_view(view) catch { _ => -1 }
  let y = b.c80_frozen_push_view(view) catch { _ => -1 }
  assert_eq(x, y)
  c80_state(a, b)
  x
}

///|
test "PCM bulk append accepted invalid prefix atomic sticky and ended" {
  let a = c80_encoder(16)
  let b = c80_encoder(16)
  // Pending header means nothing is accepted or validated yet.
  assert_eq(c80_push(a, b, [99][:]), 0)
  ignore(a.next())
  ignore(b.next())
  assert_eq(c80_push(a, b, [-8, 7, 0][:]), 3)
  let before = a.pcm.copy()
  assert_eq(c80_push(a, b, [1, 2, 8][:]), -1)
  assert_eq(a.pcm, before)
  assert_eq(c80_push(a, b, [0][:]), -1)
  let c = c80_encoder(16)
  let d = c80_encoder(16)
  ignore(c.next())
  ignore(d.next())
  assert_eq(c80_push(c, d, [0, 1][:]), 2)
  c.finish()
  d.finish()
  assert_eq(c80_push(c, d, [0][:]), -1)
}

///|
test "PCM bulk append unaccepted invalid tail offsets ownership and zero room" {
  let a = c80_encoder(16)
  let b = c80_encoder(16)
  ignore(a.next())
  ignore(b.next())
  let source = Array::makei(36, i => {
    if i == 0 || i >= 33 {
      99
    } else {
      i % 16 - 8
    }
  })
  let input_before = source.copy()
  assert_eq(c80_push(a, b, source[1:]), 32)
  assert_eq(source, input_before)
  let retained = a.pcm.copy()
  source[1] = 99
  assert_eq(a.pcm, retained)
  assert_eq(c80_push(a, b, source[33:]), 0)
  assert_eq(c80_push(a, b, source[0:0]), 0)
  let first = match a.next() {
    EncodedBytes(x) => x
    _ => b""
  }
  let reference = match b.next() {
    EncodedBytes(x) => x
    _ => b""
  }
  assert_eq(first, reference)
  let snapshot = first[:].to_owned()
  c80_state(a, b)
  assert_eq(c80_push(a, b, [-8, 7][:]), 2)
  assert_eq(first, snapshot)
}

///|
test "PCM bulk append growth repeated views and bounded buffer" {
  for block in [16, 257, 65535] {
    let a = c80_encoder(block)
    let b = c80_encoder(block)
    ignore(a.next())
    ignore(b.next())
    let source = Array::makei(block * 2 + 2, i => i % 16 - 8)
    let mut at = 1
    for chunk in [1, 7, 8, 17, 256, 1024, 131070] {
      let remaining = source.length() - 1 - at
      let n = if chunk < remaining { chunk } else { remaining }
      assert_eq(c80_push(a, b, source[at:at + n]), n)
      at += n
    }
    assert_eq(a.pcm.length(), block * 2)
    assert_eq(a.peak_pcm, block * 2)
    source[1] = 99
    c80_state(a, b)
  }
}
