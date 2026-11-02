///|
/// Decode a half-open sample interval using native SEEKTABLE offsets. Only the
/// selected frames are CRC-verified; STREAMINFO MD5 cannot be verified without
/// decoding the whole stream. The result explicitly reports FrameCrcOnly.
/// A missing usable point starts at the first frame. Invalid selected points
/// are errors, never silently ignored or recovered by scanning for sync bytes.
/// An empty interval reads metadata only; if total_samples is unknown, its
/// endpoint is not proven to lie inside the stream. Use build_index for that.
pub fn decode_seektable_range(
  data : Bytes,
  start : Int64,
  end : Int64,
) -> Audio raise FlacError {
  if start < 0L || end < start {
    raise Invalid(0L, "invalid sample interval")
  }
  let (metadata, audio_start) = parse_metadata(data) catch {
    NeedMore => raise Invalid(data.length().to_int64(), "truncated metadata")
    error => raise error
  }
  let info = metadata.info
  if info.total_samples != 0L && end > info.total_samples {
    raise Invalid(0L, "sample interval is outside stream")
  }
  let frames = []
  if start == end {
    return { metadata, frames, integrity: FrameCrcOnly, }
  }
  let mut chosen : SeekPoint? = None
  for point in metadata.seek_points {
    if point.sample <= start.to_uint64() {
      chosen = Some(point)
    } else {
      break
    }
  }
  let mut offset = audio_start
  let mut expected = 0L
  if chosen is Some(point) {
    if point.offset >= (data.length() - audio_start).to_uint64() {
      raise Invalid(
        audio_start.to_int64(),
        "seek table byte offset is outside input",
      )
    }
    offset += point.offset.to_int()
    expected = point.sample.reinterpret_as_int64()
  }
  let mut strategy : Bool? = None
  let mut first = true
  while expected < end {
    let (frame, next) = parse_frame(data, offset, info, offset.to_int64()) catch {
      NeedMore =>
        raise Invalid(
          offset.to_int64(),
          "truncated frame while seeking sample interval",
        )
      error => raise error
    }
    let actual = if frame.variable_block {
      frame.number
    } else {
      frame.number * info.max_block_size.to_int64()
    }
    if actual != expected {
      raise Invalid(
        offset.to_int64(),
        "seek frame sample number does not match requested location",
      )
    }
    if first {
      if chosen is Some(point) {
        if point.samples != frame.block_size {
          raise Invalid(
            offset.to_int64(),
            "seek point block size does not match frame",
          )
        }
      }
      first = false
    }
    if strategy is Some(previous) {
      if previous != frame.variable_block {
        raise Invalid(
          offset.to_int64(),
          "blocking strategy changed while seeking",
        )
      }
    }
    strategy = Some(frame.variable_block)
    if frame.block_size > info.max_block_size ||
      (next < data.length() && frame.block_size < info.min_block_size) ||
      (
        !frame.variable_block &&
        next < data.length() &&
        frame.block_size != info.max_block_size
      ) {
      raise Invalid(offset.to_int64(), "invalid block size while seeking")
    }
    let frame = { ..frame, sample_number: actual, }
    if crop_frame(frame, start, end) is Some(cropped) {
      frames.push(cropped)
    }
    expected += frame.block_size.to_int64()
    if info.total_samples != 0L && expected > info.total_samples {
      raise Invalid(offset.to_int64(), "frame exceeds STREAMINFO sample count")
    }
    offset = next
  }
  { metadata, frames, integrity: FrameCrcOnly, }
}
