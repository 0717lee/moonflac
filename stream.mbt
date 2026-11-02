///|
/// STREAMINFO MD5 validation at the end of a complete stream.
pub(all) enum Integrity {
  Md5Verified
  Md5Unavailable
  FrameCrcOnly
} derive(Show, Debug, Eq)

///|
/// Pull one event at a time; PCM arrays belong to the caller.
pub(all) enum DecodeEvent {
  MetadataReady(Metadata)
  AudioFrame(Frame)
  LinkEnd(Integrity)
  NeedInput
  Done(Integrity)
}

///|
/// An incremental decoder. push accepts a prefix; drain next before retrying
/// the remainder. finish declares EOF, then next validates length and MD5.
struct Decoder {
  mut pending : Bytes
  incoming : Array[Byte]
  mut retry_at : Int32
  mut offset : Int64
  mut metadata : Metadata?
  mut ended : Bool
  mut completed : Integrity?
  mut failed : FlacError?
  mut samples : Int64
  mut frame_count : Int64
  mut strategy : Bool?
  mut short_block : Bool
  mut first_block : Int32
  mut previous_block : Int32
  mut properties_changed : Bool
  mut digest : Md5
  limit : Int32
  mut peak : Int32
  mut container : Int32
  mut ogg : OggDemux?
}

///|
/// max_buffer_bytes limits retained compressed native bytes; Ogg also bounds
/// its partial packet to this value. A caller can raise it for large metadata.
pub fn Decoder::new(max_buffer_bytes~ : Int32 = 33554432) -> Decoder {
  {
    pending: b"",
    incoming: [],
    retry_at: 0,
    offset: 0L,
    metadata: None,
    ended: false,
    completed: None,
    failed: None,
    samples: 0L,
    frame_count: 0L,
    strategy: None,
    short_block: false,
    first_block: 0,
    previous_block: 0,
    properties_changed: false,
    digest: Md5::new(),
    limit: max_buffer_bytes,
    peak: 0,
    container: 0,
    ogg: None,
  }
}

///|
/// Current retained compressed native bytes (not output PCM).
pub fn Decoder::buffered_bytes(self : Decoder) -> Int32 {
  self.pending.length() + self.incoming.length()
}

///|
/// Peak retained native compressed bytes, for resource accounting.
pub fn Decoder::peak_buffered_bytes(self : Decoder) -> Int32 {
  self.peak
}

///|
/// Native compressed staging plus the Ogg page and partial packet, if present.
pub fn Decoder::compressed_storage_bytes(self : Decoder) -> Int64 {
  let ogg_bytes = match self.ogg {
    Some(ogg) => ogg.buffered_bytes()
    None => 0
  }
  self.buffered_bytes().to_int64() + ogg_bytes.to_int64()
}

///|
/// Conservative upper bound on peak retained compressed bytes. Independent
/// native and Ogg peaks can occur at different times; PCM is caller-owned.
pub fn Decoder::peak_compressed_storage_bytes(self : Decoder) -> Int64 {
  let ogg_bytes = match self.ogg {
    Some(ogg) => ogg.peak_buffered_bytes()
    None => 0
  }
  self.peak.to_int64() + ogg_bytes.to_int64()
}

///|
/// Supply input and return the number of bytes accepted. Input is copied.
pub fn Decoder::push(self : Decoder, input : Bytes) -> Int32 raise FlacError {
  self.push_input(input) catch {
    error => {
      self.failed = Some(error)
      raise error
    }
  }
}

///|
fn Decoder::push_input(self : Decoder, input : Bytes) -> Int32 raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  if self.ended {
    raise Invalid(self.offset, "input supplied after finish")
  }
  if self.limit < 4 {
    raise Limit("compressed buffer limit must be at least four")
  }
  let room = self.limit - self.buffered_bytes()
  if room <= 0 {
    raise Limit("compressed buffer full; drain frames or raise limit")
  }
  let capacity = if room < 16384 { room } else { 16384 }
  let count = if input.length() < capacity { input.length() } else { capacity }
  if count == 0 {
    return 0
  }
  let bytes = input[:count].to_owned()
  if self.container == 2 {
    if self.ogg is Some(ogg) {
      for packet in ogg.push(bytes) {
        self.append_native(packet)
      }
    }
  } else {
    self.append_native(bytes)
    if self.container == 0 && self.buffered_bytes() >= 4 {
      self.flush_input()
      if self.pending[:4] == b"OggS" {
        let ogg = OggDemux::new(max_packet_bytes=self.limit)
        self.ogg = Some(ogg)
        self.container = 2
        let initial = self.pending
        self.pending = b""
        for packet in ogg.push(initial) {
          self.append_native(packet)
        }
      } else {
        self.container = 1
      }
    }
  }
  count
}

///|
fn Decoder::append_native(
  self : Decoder,
  bytes : Bytes,
) -> Unit raise FlacError {
  if bytes.length() > self.limit - self.buffered_bytes() {
    raise Limit("compressed buffer limit exceeded")
  }
  for byte in bytes {
    self.incoming.push(byte)
  }
  if self.buffered_bytes() > self.peak {
    self.peak = self.buffered_bytes()
  }
}

///|
/// Declare end of input. Call next until Done or an explicit error.
pub fn Decoder::finish(self : Decoder) -> Unit raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  if !self.ended {
    if self.ogg is Some(ogg) {
      ogg.finish() catch {
        error => {
          self.failed = Some(error)
          raise error
        }
      }
    }
    self.ended = true
  }
}

///|
/// Errors are terminal and repeated on later calls.
pub fn Decoder::next(self : Decoder) -> DecodeEvent raise FlacError {
  if self.failed is Some(error) {
    raise error
  }
  if !self.ended && self.buffered_bytes() < self.retry_at {
    return NeedInput
  }
  self.flush_input()
  let event = self.read_event() catch {
    NeedMore => {
      if self.ended {
        let error = Invalid(
          self.offset + self.pending.length().to_int64(),
          "truncated FLAC stream",
        )
        self.failed = Some(error)
        raise error
      }
      let size = self.pending.length()
      self.retry_at = if size == 0 {
        1
      } else if size > self.limit / 2 {
        self.limit
      } else {
        size * 2
      }
      return NeedInput
    }
    error => {
      self.failed = Some(error)
      raise error
    }
  }
  self.retry_at = 0
  event
}

///|
/// Materialize only when a parse attempt is due. Geometric retry thresholds
/// bound re-reading under one-byte input; finish forces the final attempt.
fn Decoder::flush_input(self : Decoder) -> Unit {
  if !self.incoming.is_empty() {
    self.pending = self.pending + Bytes::from_array(self.incoming)
    self.incoming.clear()
  }
}

///|
fn Decoder::read_event(self : Decoder) -> DecodeEvent raise FlacError {
  if self.completed is Some(integrity) {
    return Done(integrity)
  }
  let metadata = match self.metadata {
    Some(value) => value
    None => {
      let (metadata, consumed) = parse_metadata(
        self.pending,
        max_metadata_bytes=self.limit,
      )
      self.pending = self.pending[consumed:].to_owned()
      self.offset += consumed.to_int64()
      self.metadata = Some(metadata)
      return MetadataReady(metadata)
    }
  }
  if self.container == 2 && !self.pending.is_empty() && self.pending[0] == 102 {
    if self.pending.length() < 4 {
      raise NeedMore
    }
    if self.pending[:4] == b"fLaC" {
      let integrity = self.verify_end(metadata)
      self.metadata = None
      self.samples = 0L
      self.frame_count = 0L
      self.strategy = None
      self.short_block = false
      self.first_block = 0
      self.previous_block = 0
      self.properties_changed = false
      self.digest = Md5::new()
      return LinkEnd(integrity)
    }
  }
  if self.pending.is_empty() {
    if !self.ended {
      return NeedInput
    }
    let integrity = self.verify_end(metadata)
    self.completed = Some(integrity)
    return Done(integrity)
  }
  let (frame, consumed) = parse_frame(
    self.pending,
    0,
    metadata.info,
    self.offset,
  )
  if frame.block_size > metadata.info.max_block_size {
    raise Invalid(self.offset, "block exceeds STREAMINFO maximum")
  }
  let different_properties = frame.channels.length() != metadata.info.channels ||
    frame.bits_per_sample != metadata.info.bits_per_sample ||
    frame.sample_rate != metadata.info.sample_rate
  if self.frame_count > 0L && different_properties {
    self.properties_changed = true
  }
  // Changing-format streams may retain the original format's byte-size hints
  // (Appendix C.8; public uncommon 01-04). Buffers never depend on these hints.
  if !self.properties_changed &&
    (
      (
        metadata.info.max_frame_size != 0 &&
        consumed > metadata.info.max_frame_size
      ) ||
      (
        metadata.info.min_frame_size != 0 &&
        consumed < metadata.info.min_frame_size
      )
    ) {
    raise Invalid(self.offset, "frame size outside STREAMINFO range")
  }
  if self.frame_count == 0L && different_properties {
    raise Invalid(
      self.offset,
      "initial frame properties disagree with STREAMINFO",
    )
  }
  if self.frame_count > 0L && self.previous_block < metadata.info.min_block_size {
    raise Invalid(
      self.offset,
      "block below STREAMINFO minimum is only valid as final frame",
    )
  }
  if self.strategy is Some(strategy) {
    if strategy != frame.variable_block {
      raise Invalid(self.offset, "blocking strategy changed")
    }
  } else {
    self.strategy = Some(frame.variable_block)
    self.first_block = frame.block_size
  }
  if frame.variable_block {
    if frame.number != self.samples {
      raise Invalid(self.offset, "noncontiguous sample number")
    }
  } else {
    if frame.number != self.frame_count {
      raise Invalid(self.offset, "noncontiguous frame number")
    }
    if self.short_block || frame.block_size > self.first_block {
      raise Invalid(self.offset, "invalid fixed-block sequence")
    }
    if frame.block_size < self.first_block {
      self.short_block = true
    }
  }
  let frame = { ..frame, sample_number: self.samples, }
  self.samples += frame.block_size.to_int64()
  if metadata.info.total_samples != 0L &&
    self.samples > metadata.info.total_samples {
    raise Invalid(self.offset, "decoded samples exceed STREAMINFO")
  }
  self.frame_count += 1L
  self.previous_block = frame.block_size
  md5_update_frame(self.digest, frame)
  self.pending = self.pending[consumed:].to_owned()
  self.offset += consumed.to_int64()
  AudioFrame(frame)
}

///|
/// Whole-file convenience API. Frame buffers are owned by the returned value.
pub(all) struct Audio {
  metadata : Metadata
  frames : Array[Frame]
  integrity : Integrity
}

///|
fn Decoder::verify_end(
  self : Decoder,
  metadata : Metadata,
) -> Integrity raise FlacError {
  if self.frame_count == 0L {
    raise Invalid(self.offset, "FLAC stream contains no audio frame")
  }
  if metadata.info.total_samples != 0L &&
    metadata.info.total_samples != self.samples {
    raise Invalid(self.offset, "sample count does not match STREAMINFO")
  }
  let mut available = false
  for byte in metadata.info.md5 {
    if byte != 0 {
      available = true
    }
  }
  if available {
    if self.digest.digest() != metadata.info.md5 {
      raise Invalid(self.offset, "STREAMINFO MD5 mismatch")
    }
    Md5Verified
  } else {
    Md5Unavailable
  }
}

///|
/// Decode native FLAC or Ogg FLAC with complete integrity validation.
pub fn decode(data : Bytes) -> Audio raise FlacError {
  let links = decode_chained(data)
  if links.length() != 1 {
    raise Invalid(0L, "multiple Ogg links; use decode_chained")
  }
  links[0]
}

///|
/// Decode every logical FLAC link of an Ogg chain, or one native stream.
pub fn decode_chained(data : Bytes) -> Array[Audio] raise FlacError {
  let decoder = Decoder::new()
  let mut frames = []
  let links = []
  let mut metadata = None
  let mut cursor = 0
  while true {
    match decoder.next() {
      MetadataReady(value) => metadata = Some(value)
      AudioFrame(frame) => frames.push(frame)
      LinkEnd(integrity) => {
        match metadata {
          Some(metadata) => links.push({ metadata, frames, integrity, })
          None => raise Invalid(0L, "missing link metadata")
        }
        metadata = None
        frames = []
      }
      Done(integrity) =>
        match metadata {
          Some(metadata) => {
            links.push({ metadata, frames, integrity, })
            return links
          }
          None => raise Invalid(0L, "missing STREAMINFO")
        }
      NeedInput =>
        if cursor < data.length() {
          let end = if data.length() - cursor > 16384 {
            cursor + 16384
          } else {
            data.length()
          }
          cursor += decoder.push(data[cursor:end].to_owned())
        } else {
          decoder.finish()
        }
    }
  } nobreak {
    raise Invalid(0L, "decoder ended without result")
  }
}
