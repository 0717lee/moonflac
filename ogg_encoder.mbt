///|
/// Ogg FLAC muxing. The audio frames and STREAMINFO are produced by the
/// native encoder; this module only adds the Ogg mapping and page framing.
/// The output is one logical stream and is validated by OggDemux on the
/// reverse path.
const OGG_FLAC_SERIAL : UInt32 = 0x4d464c43U

///|
const OGG_MAX_PAGE_DATA : Int32 = 65025

///|
const OGG_MAX_PACKET_CHUNK : Int32 = 65024

///|
fn ogg_write_le32(out : Array[Byte], value : UInt32) -> Unit {
  for i = 0; i < 4; i = i + 1 {
    out.push((value >> (i * 8)).to_byte())
  }
}

///|
fn ogg_write_le64(out : Array[Byte], value : UInt64) -> Unit {
  for i = 0; i < 8; i = i + 1 {
    out.push((value >> (i * 8)).to_byte())
  }
}

///|
/// Build one Ogg page for a packet chunk. The lacing table is derived from
/// the chunk length; callers must keep a non-final chunk at a multiple of 255
/// bytes so the packet is marked as continuing without a terminator.
fn ogg_make_page(
  packet : Bytes,
  flags : Byte,
  granule : UInt64,
  serial : UInt32,
  sequence : UInt32,
) -> Bytes raise FlacError {
  let lacing : Array[Byte] = []
  let mut remaining = packet.length()
  while remaining >= 255 {
    lacing.push(255)
    remaining -= 255
  }
  lacing.push(remaining.to_byte())
  if lacing.length() > 255 {
    raise Limit("Ogg page requires more than 255 lacing values")
  }
  let page : Array[Byte] = [79, 103, 103, 83, 0, flags]
  ogg_write_le64(page, granule)
  ogg_write_le32(page, serial)
  ogg_write_le32(page, sequence)
  for _i = 0; _i < 4; _i = _i + 1 {
    page.push(0)
  }
  page.push(lacing.length().to_byte())
  for value in lacing {
    page.push(value)
  }
  for byte in packet {
    page.push(byte)
  }
  let crc = ogg_crc(page)
  for i = 0; i < 4; i = i + 1 {
    page[22 + i] = (crc >> (i * 8)).to_byte()
  }
  Bytes::from_array(page)
}

///|
/// Split a packet into pages. A packet larger than one page is represented by
/// full 255-lacing pages followed by a terminating page. Intermediate pages
/// carry a continuation flag and, for audio, an unknown granule.
fn ogg_packet_pages(
  packet : Bytes,
  serial : UInt32,
  first_sequence : UInt32,
  granule : UInt64,
  eos : Bool,
) -> (Array[Bytes], UInt32) raise FlacError {
  let pages : Array[Bytes] = []
  let mut offset = 0
  let mut sequence = first_sequence
  let mut first = true
  while packet.length() - offset > OGG_MAX_PACKET_CHUNK {
    let remaining = packet.length() - offset
    let take = if remaining == OGG_MAX_PAGE_DATA {
      64770
    } else {
      OGG_MAX_PAGE_DATA
    }
    let chunk = packet[offset:offset + take].to_owned()
    let flags = if first { 0 } else { 1 }
    pages.push(
      ogg_make_page(
        chunk,
        flags.to_byte(),
        0xffffffffffffffffUL,
        serial,
        sequence,
      ),
    )
    offset += take
    sequence += 1U
    first = false
  }
  let tail = packet[offset:].to_owned()
  let flags = if first { if eos { 4 } else { 0 } } else if eos { 5 } else { 1 }
  pages.push(ogg_make_page(tail, flags.to_byte(), granule, serial, sequence))
  (pages, sequence + 1U)
}

///|
fn ogg_metadata_block(block : Bytes, last : Bool) -> Bytes raise FlacError {
  if block.length() < 4 {
    raise Invalid(0L, "truncated native FLAC metadata block")
  }
  let out = block.to_array()
  let flags = out[0].to_int()
  out[0] = if last { (flags | 128).to_byte() } else { (flags & 127).to_byte() }
  Bytes::from_array(out)
}

///|
fn ogg_first_packet(streaminfo : Bytes, header_count : Int32) -> Bytes {
  let packet : Array[Byte] = [
    127,
    70,
    76,
    65,
    67,
    1,
    0,
    (header_count >> 8).to_byte(),
    header_count.to_byte(),
  ]
  // The Ogg mapping repeats the native marker before the STREAMINFO block.
  packet.push(102)
  packet.push(76)
  packet.push(97)
  packet.push(67)
  for i = 0; i < streaminfo.length(); i = i + 1 {
    let value = if i == 0 {
      (streaminfo[i].to_int() & 127).to_byte()
    } else {
      streaminfo[i]
    }
    packet.push(value)
  }
  Bytes::from_array(packet)
}

///|
fn ogg_vorbis_comment(vendor : String) -> Bytes {
  let text = @utf8.encode(vendor)
  let payload_length = 4 + text.length() + 4
  let block : Array[Byte] = [
    132,
    (payload_length >> 16).to_byte(),
    (payload_length >> 8).to_byte(),
    payload_length.to_byte(),
  ]
  ogg_write_le32(block, text.length().to_uint())
  for byte in text {
    block.push(byte)
  }
  for _i = 0; _i < 4; _i = _i + 1 {
    block.push(0)
  }
  Bytes::from_array(block)
}

///|
/// Read the native metadata blocks, retaining their raw four-byte headers.
/// The first block must be a 34-byte STREAMINFO. Returns the blocks and the
/// first audio-frame offset.
fn ogg_native_blocks(native : Bytes) -> (Array[Bytes], Int32) raise FlacError {
  if native.length() < 42 || native[:4] != b"fLaC" {
    raise Invalid(0L, "Ogg muxing requires a native FLAC stream")
  }
  let blocks : Array[Bytes] = []
  let mut pos = 4
  let mut first = true
  while true {
    if native.length() - pos < 4 {
      raise Invalid(pos.to_int64(), "truncated FLAC metadata header")
    }
    let flags = native[pos].to_int()
    let kind = flags & 127
    let length = native[pos + 1].to_int() * 65536 +
      native[pos + 2].to_int() * 256 +
      native[pos + 3].to_int()
    if native.length() - pos - 4 < length {
      raise Invalid(pos.to_int64(), "truncated FLAC metadata payload")
    }
    if first && (kind != 0 || length != 34) {
      raise Invalid(0L, "Ogg FLAC requires STREAMINFO first")
    }
    blocks.push(native[pos:pos + 4 + length].to_owned())
    pos += 4 + length
    first = false
    if (flags & 128) != 0 {
      break
    }
  }
  (blocks, pos)
}

///|
/// Convert a complete native FLAC file into one Ogg FLAC logical stream.
/// The native stream is validated by build_index before its frames are
/// repackaged, so corrupt input cannot silently become a valid Ogg file.
pub fn ogg_from_flac(
  native : Bytes,
  serial~ : UInt32 = OGG_FLAC_SERIAL,
  vendor~ : String = "MoonFLAC",
) -> Bytes raise FlacError {
  let (blocks, first_frame) = ogg_native_blocks(native)
  if first_frame >= native.length() {
    raise Invalid(0L, "native FLAC contains no audio frames")
  }
  let metadata : Array[Bytes] = []
  for i = 1; i < blocks.length(); i = i + 1 {
    metadata.push(blocks[i])
  }
  if metadata.is_empty() {
    metadata.push(ogg_vorbis_comment(vendor))
  }
  if metadata.length() > 65535 {
    raise Limit("Ogg FLAC header packet count exceeds 16 bits")
  }
  let pages : Array[Bytes] = []
  let first = ogg_first_packet(blocks[0], metadata.length())
  pages.push(ogg_make_page(first, 2, 0UL, serial, 0U))
  let mut sequence = 1U
  for i = 0; i < metadata.length(); i = i + 1 {
    let last = i == metadata.length() - 1
    let block = ogg_metadata_block(metadata[i], last)
    let (metadata_pages, next) = ogg_packet_pages(
      block, serial, sequence, 0UL, false,
    )
    for page in metadata_pages {
      pages.push(page)
    }
    sequence = next
  }
  let index = build_index(native)
  if index.frames.is_empty() {
    raise Invalid(0L, "native FLAC contains no indexed frames")
  }
  for i = 0; i < index.frames.length(); i = i + 1 {
    let frame = index.frames[i]
    let start = frame.offset.to_int()
    let end = start + frame.bytes
    if start < 0 || end > native.length() || frame.bytes <= 0 {
      raise Invalid(frame.offset, "native FLAC frame location is out of bounds")
    }
    let packet = native[start:end].to_owned()
    let eos = i == index.frames.length() - 1
    let granule = (frame.sample + frame.samples.to_int64()).to_uint64()
    let (frame_pages, next) = ogg_packet_pages(
      packet, serial, sequence, granule, eos,
    )
    for page in frame_pages {
      pages.push(page)
    }
    sequence = next
  }
  let out = @buffer.Buffer()
  for page in pages {
    out.write_bytes(page)
  }
  out.to_bytes()
}

///|
/// Encode interleaved integer PCM and wrap the result in Ogg FLAC. This is the
/// whole-buffer convenience API; native streaming remains available separately.
pub fn encode_ogg_pcm(
  samples : Array[Int32],
  config : EncoderConfig,
  serial~ : UInt32 = OGG_FLAC_SERIAL,
  vendor~ : String = "MoonFLAC",
) -> Bytes raise FlacError {
  let native = encode_pcm(samples, config)
  ogg_from_flac(native, serial~, vendor~)
}
