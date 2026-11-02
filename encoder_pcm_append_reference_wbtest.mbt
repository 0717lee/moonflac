///|
fn Encoder::c80_frozen_push_view(
  self : Encoder,
  samples : ArrayView[Int32],
) -> Int32 raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  if self.ended {
    raise Invalid(self.samples, "PCM supplied after encoder finish")
  }
  if self.queued is Some(_) {
    return 0
  }
  let capacity = self.config.block_size * self.config.format.channels
  let room = capacity - self.pcm.length()
  let count = if samples.length() < room { samples.length() } else { room }
  let bound = 1L << (self.config.format.bits_per_sample - 1)
  // Validate the accepted prefix before changing state, so a bad chunk cannot
  // leave a partially accepted frame that might later be mistaken for success.
  for i in 0..<count {
    let value = samples[i].to_int64()
    if value < -bound || value >= bound {
      let error = Invalid(self.samples, "PCM sample outside declared bit depth")
      self.failed = Some(error)
      raise error
    }
  }
  for i in 0..<count {
    self.pcm.push(samples[i])
  }
  if self.pcm.length() > self.peak_pcm {
    self.peak_pcm = self.pcm.length()
  }
  count
}
