///|
/// Raw streams have no metadata or MD5. Skipped reports every discarded byte,
/// including initial garbage and damaged frames; it is never silent recovery.
pub(all) enum RawDecodeEvent {
  RawFrame(Frame)
  Skipped(Int64, Int32)
  RawNeedInput
  RawDone
}

///|
/// Decoder for independently framed FLAC (RFC 9639 section 9). Format changes
/// are allowed. Optional info supplies the values represented by header code 0;
/// they are not inferred from earlier frames. Returned frame sample_number is
/// the local count of successfully decoded samples; number retains the original
/// encoded number. The receiver must use each frame's rate/depth/channels.
/// Incomplete frames are retried at geometrically increasing buffer sizes.
/// This bounds repeated parsing for tiny input chunks, with up to the current
/// partial-frame length of lookahead latency. finish always forces a retry.
struct RawDecoder {
  mut pending : Bytes
  incoming : Array[Byte]
  mut retry_at : Int32
  mut offset : Int64
  info : StreamInfo?
  limit : Int32
  mut peak : Int32
  mut ended : Bool
  mut failed : FlacError?
  mut queued : Frame?
  mut samples : Int64
}

///|
pub fn RawDecoder::new(
  info? : StreamInfo,
  max_buffer_bytes~ : Int32 = 33554432,
) -> RawDecoder {
  {
    pending: b"",
    incoming: [],
    retry_at: 0,
    offset: 0L,
    info,
    limit: max_buffer_bytes,
    peak: 0,
    ended: false,
    failed: None,
    queued: None,
    samples: 0L,
  }
}

///|
/// Copy an input prefix, returning accepted bytes. Drain next before retrying.
pub fn RawDecoder::push(
  self : RawDecoder,
  input : Bytes,
) -> Int32 raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  if self.ended {
    raise Invalid(self.offset, "raw input supplied after finish")
  }
  if self.limit < 4 {
    raise Limit("raw compressed buffer limit must be at least four")
  }
  let room = self.limit - self.buffered_bytes()
  if room <= 0 {
    raise Limit("raw compressed buffer full; drain or raise limit")
  }
  let count = if input.length() < room { input.length() } else { room }
  for i in 0..<count {
    self.incoming.push(input[i])
  }
  if self.buffered_bytes() > self.peak {
    self.peak = self.buffered_bytes()
  }
  count
}

///|
pub fn RawDecoder::buffered_bytes(self : RawDecoder) -> Int32 {
  self.pending.length() + self.incoming.length()
}

///|
pub fn RawDecoder::peak_buffered_bytes(self : RawDecoder) -> Int32 {
  self.peak
}

///|
/// Declare EOF. Drain next to RawDone; incomplete candidates raise an error.
pub fn RawDecoder::finish(self : RawDecoder) -> Unit raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  self.ended = true
}

///|
fn raw_header_info(
  data : Bytes,
  start : Int32,
  offset : Int64,
  fallback : StreamInfo?,
) -> StreamInfo raise FlacError {
  let r : FrameBits = {
    data,
    pos: start,
    bit: 0,
    base: offset - start.to_int64(),
  }
  if r.read(15) != 0x7ffcL {
    r.bad("invalid raw sync")
  }
  let variable = r.read(1) != 0L
  let block = r.read(4).to_int()
  let rate = r.read(4).to_int()
  let assignment = r.read(4).to_int()
  let depth = r.read(3).to_int()
  if r.read(1) != 0L ||
    block == 0 ||
    rate == 15 ||
    assignment > 10 ||
    depth == 3 {
    r.bad("reserved raw header value")
  }
  ignore(frame_number(r, variable))
  if block == 6 {
    ignore(r.read(8))
  }
  if block == 7 {
    ignore(r.read(16))
  }
  if rate == 12 {
    ignore(r.read(8))
  }
  if rate == 13 || rate == 14 {
    ignore(r.read(16))
  }
  let crc = frame_crc(data, start, r.pos, 8)
  if r.read(8).to_int() != crc {
    r.bad("raw header CRC8 mismatch")
  }
  if fallback is None && (rate == 0 || depth == 0) {
    raise Limit(
      "raw frame header requires explicit StreamInfo sample rate/bit depth",
    )
  }
  let info = fallback.unwrap_or({
    min_block_size: 16,
    max_block_size: 65535,
    min_frame_size: 0,
    max_frame_size: 0,
    sample_rate: 1,
    channels: 1,
    bits_per_sample: 4,
    total_samples: 0L,
    md5: b"",
  })
  if (rate == 0 && (info.sample_rate < 0 || info.sample_rate > 1048575)) ||
    (depth == 0 && (info.bits_per_sample < 4 || info.bits_per_sample > 32)) {
    raise Limit("invalid explicit raw StreamInfo sample rate/bit depth")
  }
  info
}

///|
fn RawDecoder::discard(self : RawDecoder, count : Int32) -> RawDecodeEvent {
  let offset = self.offset
  self.pending = self.pending[count:].to_owned()
  self.offset += count.to_int64()
  self.retry_at = 0
  Skipped(offset, count)
}

///|
/// Header CRC8 and complete frame CRC16 must pass before any PCM is emitted.
/// Every resynchronization is reported. A truncated candidate at EOF is an
/// error; a fully rejected candidate is reported as discarded bytes.
pub fn RawDecoder::next(self : RawDecoder) -> RawDecodeEvent raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  self.read_raw_event() catch {
    error => {
      self.failed = Some(error)
      raise error
    }
  }
}

///|
fn RawDecoder::read_raw_event(
  self : RawDecoder,
) -> RawDecodeEvent raise FlacError {
  if self.queued is Some(frame) {
    self.queued = None
    return RawFrame(frame)
  }
  if !self.ended && self.buffered_bytes() < self.retry_at {
    return RawNeedInput
  }
  if !self.incoming.is_empty() {
    self.pending = self.pending + Bytes::from_array(self.incoming)
    self.incoming.clear()
  }
  if self.pending.is_empty() {
    return if self.ended { RawDone } else { RawNeedInput }
  }
  let mut first_incomplete = -1
  for start = 0; start < self.pending.length(); start = start + 1 {
    if self.pending[start] != 0xff {
      continue
    }
    if start + 1 == self.pending.length() {
      if first_incomplete < 0 {
        first_incomplete = start
      }
      break
    }
    if (self.pending[start + 1].to_int() & 0xfe) != 0xf8 {
      continue
    }
    let info = raw_header_info(
      self.pending,
      start,
      self.offset + start.to_int64(),
      self.info,
    ) catch {
      NeedMore => {
        first_incomplete = start
        break
      }
      Invalid(_, _) => continue
      error => raise error
    }
    let parsed = Some(
      parse_frame(self.pending, start, info, self.offset + start.to_int64()),
    ) catch {
      NeedMore => {
        // A later sync can be ordinary PCM inside this still-valid candidate.
        // Resume scanning only after this candidate is conclusively invalid.
        first_incomplete = start
        break
      }
      Invalid(_, _) => None
      error => raise error
    }
    if parsed is Some((decoded, end)) {
      let frame = { ..decoded, sample_number: self.samples, }
      self.samples += frame.block_size.to_int64()
      let previous_offset = self.offset
      self.pending = self.pending[end:].to_owned()
      self.offset += end.to_int64()
      self.retry_at = 0
      if start > 0 {
        self.queued = Some(frame)
        return Skipped(previous_offset, start)
      }
      return RawFrame(frame)
    }
  }
  if first_incomplete >= 0 {
    if first_incomplete > 0 {
      let event = self.discard(first_incomplete)
      self.defer_raw_retry()
      return event
    }
    if self.ended {
      raise Invalid(
        self.offset + self.pending.length().to_int64(),
        "truncated raw FLAC frame",
      )
    }
    if self.pending.length() >= self.limit {
      raise Limit("raw frame exceeds compressed buffer limit")
    }
    self.defer_raw_retry()
    RawNeedInput
  } else {
    self.discard(self.pending.length())
  }
}

///|
fn RawDecoder::defer_raw_retry(self : RawDecoder) -> Unit {
  let size = self.pending.length()
  self.retry_at = if size > self.limit / 2 {
    self.limit
  } else {
    let doubled = size * 2
    if doubled < 32 {
      if self.limit < 32 {
        self.limit
      } else {
        32
      }
    } else {
      doubled
    }
  }
}
