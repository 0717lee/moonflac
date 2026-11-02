///|
fn encmeta_integer(
  out : Array[Byte],
  value : UInt64,
  width : Int32,
  little~ : Bool = false,
) -> Unit {
  for i = 0; i < width; i = i + 1 {
    let shift = if little { i * 8 } else { (width - i - 1) * 8 }
    out.push((value >> shift).to_byte())
  }
}

///|
fn encmeta_comment(
  comment : VorbisComment,
  limit : Int32,
) -> Bytes raise FlacError {
  let vendor = @utf8.encode(comment.vendor)
  let mut size = 8L + vendor.length().to_int64()
  for entry in comment.entries {
    size += 4L + @utf8.encode(entry).length().to_int64()
    if size > 16777215L || size > limit.to_int64() {
      raise Limit("encoded Vorbis comment exceeds metadata byte limit")
    }
  }
  if size > 16777215L || size > limit.to_int64() {
    raise Limit("encoded Vorbis comment exceeds metadata byte limit")
  }
  let out : Array[Byte] = []
  encmeta_integer(out, vendor.length().to_uint64(), 4, little=true)
  for byte in vendor {
    out.push(byte)
  }
  encmeta_integer(out, comment.entries.length().to_uint64(), 4, little=true)
  for entry in comment.entries {
    let bytes = @utf8.encode(entry)
    encmeta_integer(out, bytes.length().to_uint64(), 4, little=true)
    for byte in bytes {
      out.push(byte)
    }
  }
  Bytes::from_array(out)
}

///|
fn encmeta_serialize(
  streaminfo : Bytes,
  blocks : Array[MetadataBlock],
  limit : Int32,
) -> Bytes raise FlacError {
  let mut size = 42L
  for block in blocks {
    if block.kind < 1 || block.kind > 126 {
      raise Invalid(
        size, "encoder metadata excludes STREAMINFO and forbidden block types",
      )
    }
    if block.data.length() > 16777215 {
      raise Limit("metadata block exceeds 24-bit length")
    }
    size += 4L + block.data.length().to_int64()
    if size > limit.to_int64() {
      raise Limit("encoder metadata byte limit")
    }
  }
  if size > limit.to_int64() {
    raise Limit("encoder metadata byte limit")
  }
  let out : Array[Byte] = [
    102,
    76,
    97,
    67,
    if blocks.is_empty() {
      128
    } else {
      0
    },
    0,
    0,
    34,
  ]
  for byte in streaminfo {
    out.push(byte)
  }
  for i = 0; i < blocks.length(); i = i + 1 {
    let block = blocks[i]
    out.push(
      (block.kind | (if i == blocks.length() - 1 { 128 } else { 0 })).to_byte(),
    )
    encmeta_integer(out, block.data.length().to_uint64(), 3)
    for byte in block.data {
      out.push(byte)
    }
  }
  Bytes::from_array(out)
}

///|
/// Build a native header with encoder-owned STREAMINFO and caller metadata.
/// Zero statistics represent an unfinished stream. Finalization can replace
/// the first 42 bytes while retaining metadata and the first-frame offset.
fn encoder_header(
  config : EncoderConfig,
  total_samples : Int64,
  md5 : Bytes,
  min_frame_size : Int32,
  max_frame_size : Int32,
) -> Bytes raise FlacError {
  let format = config.format
  if format.sample_rate < 0 ||
    format.sample_rate > 1048575 ||
    (format.sample_rate == 0 && !config.non_audio) ||
    format.channels < 1 ||
    format.channels > 8 ||
    format.bits_per_sample < 4 ||
    format.bits_per_sample > 32 ||
    config.block_size < 16 ||
    config.block_size > 65535 {
    raise Invalid(0L, "invalid encoder stream format")
  }
  if total_samples < 0L || total_samples > 0xfffffffffL {
    raise Invalid(0L, "encoder sample count exceeds 36-bit range")
  }
  if md5.length() != 16 {
    raise Invalid(0L, "STREAMINFO MD5 must contain 16 bytes")
  }
  if min_frame_size < 0 ||
    max_frame_size < 0 ||
    min_frame_size > 16777215 ||
    max_frame_size > 16777215 ||
    (max_frame_size != 0 && min_frame_size > max_frame_size) {
    raise Invalid(0L, "invalid encoder frame size statistics")
  }
  let streaminfo : Array[Byte] = []
  encmeta_integer(
    streaminfo,
    (if config.variable_block { 16 } else { config.block_size }).to_uint64(),
    2,
  )
  encmeta_integer(streaminfo, config.block_size.to_uint64(), 2)
  encmeta_integer(streaminfo, min_frame_size.to_uint64(), 3)
  encmeta_integer(streaminfo, max_frame_size.to_uint64(), 3)
  let packed = (format.sample_rate.to_uint64() << 44) |
    ((format.channels - 1).to_uint64() << 41) |
    ((format.bits_per_sample - 1).to_uint64() << 36) |
    total_samples.reinterpret_as_uint64()
  encmeta_integer(streaminfo, packed, 8)
  for byte in md5 {
    streaminfo.push(byte)
  }
  let info_bytes = Bytes::from_array(streaminfo)
  let header = encmeta_serialize(
    info_bytes,
    config.metadata,
    config.max_metadata_bytes,
  )
  let (parsed, _) = parse_metadata(
    header,
    max_metadata_bytes=config.max_metadata_bytes,
  )
  let existing_mask = parsed.channel_mask()
  match config.channel_mask {
    None => header
    Some(mask) =>
      match existing_mask {
        Some(existing) => {
          if existing != mask {
            raise Invalid(
              0L, "encoder channel mask conflicts with supplied Vorbis comment",
            )
          }
          header
        }
        None => {
          let entries = match parsed.comments {
            Some(comment) => comment.entries.map(entry => entry)
            None => []
          }
          entries.push(
            "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x" + mask.to_string(radix=16),
          )
          let vendor = match parsed.comments {
            Some(comment) => comment.vendor
            None => "MoonFLAC"
          }
          let comment = encmeta_comment(
            { vendor, entries, },
            config.max_metadata_bytes,
          )
          let blocks = config.metadata.map(block => {
            if block.kind == 4 {
              MetadataBlock::{ kind: 4, data: comment, }
            } else {
              block
            }
          })
          if parsed.comments is None {
            blocks.push({ kind: 4, data: comment, })
          }
          let result = encmeta_serialize(
            info_bytes,
            blocks,
            config.max_metadata_bytes,
          )
          let _ = parse_metadata(
            result,
            max_metadata_bytes=config.max_metadata_bytes,
          )
          result
        }
      }
  }
}
