///|
/// Raw blocks are retained, including reserved types 7..126.
#derive(Show)
pub(all) struct MetadataBlock {
  kind : Int32
  data : Bytes
}

///|
#derive(Show)
pub(all) struct SeekPoint {
  sample : UInt64
  offset : UInt64
  samples : Int32
}

///|
#derive(Show)
pub(all) struct VorbisComment {
  vendor : String
  entries : Array[String]
}

///|
#derive(Show)
pub(all) struct CueIndex {
  offset : UInt64
  number : Int32
}

///|
#derive(Show)
pub(all) struct CueTrack {
  offset : UInt64
  number : Int32
  isrc : Bytes
  non_audio : Bool
  pre_emphasis : Bool
  indices : Array[CueIndex]
}

///|
#derive(Show)
pub(all) struct CueSheet {
  catalog : Bytes
  lead_in : UInt64
  is_cd : Bool
  tracks : Array[CueTrack]
}

///|
#derive(Show)
pub(all) struct Picture {
  kind : UInt32
  media_type : String
  description : String
  width : UInt32
  height : UInt32
  depth : UInt32
  colors : UInt32
  data : Bytes
}

///|
#derive(Show)
pub(all) struct Metadata {
  info : StreamInfo
  blocks : Array[MetadataBlock]
  seek_points : Array[SeekPoint]
  comments : VorbisComment?
  cuesheet : CueSheet?
  cuesheets : Array[CueSheet]
  pictures : Array[Picture]
}

///|
priv struct MetaReader {
  data : Bytes
  base : Int32
  mut pos : Int32
}

///|
fn MetaReader::bad(r : MetaReader, message : String) -> Unit raise FlacError {
  raise Invalid((r.base + r.pos).to_int64(), message)
}

///|
fn MetaReader::take(r : MetaReader, n : Int32) -> Bytes raise FlacError {
  if n < 0 || n > r.data.length() - r.pos {
    r.bad("metadata field exceeds block")
  }
  let result : FixedArray[Byte] = FixedArray::make(n, 0)
  for i = 0; i < n; i = i + 1 {
    result[i] = r.data[r.pos + i]
  }
  r.pos += n
  Bytes::from_fixedarray(result)
}

///|
fn MetaReader::uint(
  r : MetaReader,
  n : Int32,
  little~ : Bool = false,
) -> UInt64 raise FlacError {
  let b = r.take(n)
  let mut v = 0UL
  for i = 0; i < n; i = i + 1 {
    let j = if little { n - 1 - i } else { i }
    v = (v << 8) | b[j].to_uint64()
  }
  v
}

///|
fn MetaReader::size(
  r : MetaReader,
  little~ : Bool = false,
) -> Int32 raise FlacError {
  let n = r.uint(4, little~)
  if n > (r.data.length() - r.pos).to_uint64() {
    r.bad("metadata length exceeds block")
  }
  n.to_int()
}

///|
fn MetaReader::text(r : MetaReader, n : Int32) -> String raise FlacError {
  let b = r.take(n)
  @utf8.decode(b) catch {
    _ => {
      r.bad("invalid metadata UTF-8")
      ""
    }
  }
}

///|
fn MetaReader::zero(r : MetaReader, n : Int32) -> Unit raise FlacError {
  for b in r.take(n) {
    if b != 0 {
      r.bad("nonzero reserved metadata bits")
    }
  }
}

///|
fn MetaReader::end(r : MetaReader) -> Unit raise FlacError {
  if r.pos != r.data.length() {
    r.bad("trailing metadata bytes")
  }
}

///|
fn meta_cue(r : MetaReader) -> CueSheet raise FlacError {
  let catalog = r.take(128)
  let mut padding = false
  for b in catalog {
    if b == 0 {
      padding = true
    } else if padding || b < 32 || b > 126 {
      r.bad("invalid catalog number")
    }
  }
  let lead_in = r.uint(8)
  let flags = r.uint(1).to_int()
  if (flags & 127) != 0 {
    r.bad("reserved cuesheet flags")
  }
  let is_cd = (flags & 128) != 0
  r.zero(258)
  let count = r.uint(1).to_int()
  if count == 0 || (is_cd && (count > 100 || lead_in < 88200UL)) {
    r.bad("invalid cuesheet track count or lead-in")
  }
  let tracks = []
  let seen : Array[Int32] = []
  for t = 0; t < count; t = t + 1 {
    let offset = r.uint(8)
    let number = r.uint(1).to_int()
    let leadout = t == count - 1
    if number == 0 ||
      seen.contains(number) ||
      (leadout && number != (if is_cd { 170 } else { 255 })) ||
      (is_cd && !leadout && number > 99) ||
      (is_cd && offset % 588UL != 0UL) {
      r.bad("invalid cuesheet track")
    }
    seen.push(number)
    let isrc = r.take(12)
    let mut empty = true
    for b in isrc {
      if b != 0 {
        empty = false
      }
    }
    if !empty {
      for b in isrc {
        if !((b >= 48 && b <= 57) ||
          (b >= 65 && b <= 90) ||
          (b >= 97 && b <= 122)) {
          r.bad("invalid ISRC")
        }
      }
    }
    let flags = r.uint(1).to_int()
    if (flags & 63) != 0 {
      r.bad("reserved track flags")
    }
    r.zero(13)
    let count = r.uint(1).to_int()
    if (leadout && count != 0) ||
      (!leadout && count == 0) ||
      (is_cd && count > 100) {
      r.bad("invalid cue index count")
    }
    let indices = []
    let mut last = -1
    for j = 0; j < count; j = j + 1 {
      let offset = r.uint(8)
      let number = r.uint(1).to_int()
      r.zero(3)
      if (j == 0 && number > 1) ||
        (j > 0 && number != last + 1) ||
        (is_cd && offset % 588UL != 0UL) {
        r.bad("invalid cue index")
      }
      last = number
      indices.push(CueIndex::{ offset, number, })
    }
    tracks.push(CueTrack::{
      offset,
      number,
      isrc,
      non_audio: (flags & 128) != 0,
      pre_emphasis: (flags & 64) != 0,
      indices,
    })
  }
  r.end()
  { catalog, lead_in, is_cd, tracks, }
}

///|
/// Parse native metadata; incomplete input raises NeedMore. Limits apply before copying payloads.
pub fn parse_metadata(
  data : Bytes,
  max_metadata_bytes~ : Int32 = 67108864,
) -> (Metadata, Int32) raise FlacError {
  if data.length() < 4 {
    raise NeedMore
  }
  if data[0] != 102 || data[1] != 76 || data[2] != 97 || data[3] != 67 {
    raise Invalid(0, "missing fLaC signature")
  }
  let mut pos = 4
  let mut info : StreamInfo? = None
  let blocks = []
  let seek_points = []
  let mut comments = None
  let mut cuesheet = None
  let cuesheets = []
  let pictures : Array[Picture] = []
  let mut seen_seek = false
  while true {
    if data.length() - pos < 4 {
      raise NeedMore
    }
    let flags = data[pos].to_int()
    let kind = flags & 127
    let n = (data[pos + 1].to_int() << 16) |
      (data[pos + 2].to_int() << 8) |
      data[pos + 3].to_int()
    if kind == 127 || (pos == 4 && kind != 0) {
      raise Invalid(pos.to_int64(), "invalid metadata type/order")
    }
    if n > max_metadata_bytes - pos - 4 {
      raise Limit("metadata byte limit")
    }
    if n > data.length() - pos - 4 {
      raise NeedMore
    }
    let source = MetaReader::{ data, base: 0, pos: pos + 4, }
    let payload = source.take(n)
    let r = MetaReader::{ data: payload, base: pos + 4, pos: 0, }
    match kind {
      0 => {
        if info is Some(_) || n != 34 {
          r.bad("duplicate or invalid STREAMINFO")
        }
        let min_block_size = r.uint(2).to_int()
        let max_block_size = r.uint(2).to_int()
        let min_frame_size = r.uint(3).to_int()
        let max_frame_size = r.uint(3).to_int()
        let packed = r.uint(8)
        let sample_rate = (packed >> 44).to_int()
        let channels = ((packed >> 41) & 7UL).to_int() + 1
        let bits_per_sample = ((packed >> 36) & 31UL).to_int() + 1
        let total_samples = (packed & 0xfffffffffUL).to_int64()
        let md5 = r.take(16)
        if min_block_size < 16 ||
          max_block_size < min_block_size ||
          bits_per_sample < 4 ||
          (max_frame_size != 0 && min_frame_size > max_frame_size) {
          r.bad("invalid STREAMINFO ranges")
        }
        info = Some({
          min_block_size,
          max_block_size,
          min_frame_size,
          max_frame_size,
          sample_rate,
          channels,
          bits_per_sample,
          total_samples,
          md5,
        })
      }
      1 => r.zero(n)
      2 => if n < 4 { r.bad("APPLICATION missing identifier") }
      3 => {
        if seen_seek || n % 18 != 0 {
          r.bad("duplicate or malformed SEEKTABLE")
        }
        seen_seek = true
        let mut previous : UInt64? = None
        let mut placeholders = false
        for _i = 0; _i < n / 18; _i = _i + 1 {
          let sample = r.uint(8)
          let offset = r.uint(8)
          let samples = r.uint(2).to_int()
          if sample == 0xffffffffffffffffUL {
            placeholders = true
          } else {
            if placeholders {
              r.bad("seek point after placeholder")
            }
            if previous is Some(p) {
              if sample <= p {
                r.bad("unordered seek points")
              }
            }
            previous = Some(sample)
          }
          seek_points.push({ sample, offset, samples, })
        }
      }
      4 => {
        if comments is Some(_) {
          r.bad("duplicate VORBIS_COMMENT")
        }
        let vendor = r.text(r.size(little=true))
        let count = r.uint(4, little=true)
        if count > ((n - r.pos) / 4).to_uint64() {
          r.bad("comment count exceeds block")
        }
        let entries = []
        for _i = 0; _i < count.to_int(); _i = _i + 1 {
          let entry = r.text(r.size(little=true))
          let mut equal = false
          for c in entry {
            if c == '=' {
              equal = true
              break
            }
            if c.to_int() < 32 || c.to_int() > 126 {
              r.bad("invalid comment field name")
            }
          }
          if !equal {
            r.bad("comment has no field separator")
          }
          entries.push(entry)
        }
        r.end()
        comments = Some({ vendor, entries, })
      }
      5 => {
        let cue = meta_cue(r)
        if cuesheet is None {
          cuesheet = Some(cue)
        }
        cuesheets.push(cue)
      }
      6 => {
        let kind = r.uint(4).to_uint()
        let media_type = r.text(r.size())
        for c in media_type {
          if c.to_int() < 32 || c.to_int() > 126 {
            r.bad("invalid picture media type")
          }
        }
        let description = r.text(r.size())
        let width = r.uint(4).to_uint()
        let height = r.uint(4).to_uint()
        let depth = r.uint(4).to_uint()
        let colors = r.uint(4).to_uint()
        let data = r.take(r.size())
        r.end()
        if kind == 1U || kind == 2U {
          for p in pictures {
            if p.kind == kind {
              r.bad("duplicate picture icon")
            }
          }
        }
        pictures.push(Picture::{
          kind,
          media_type,
          description,
          width,
          height,
          depth,
          colors,
          data,
        })
      }
      _ => ()
    }
    blocks.push({ kind, data: payload, })
    pos += 4 + n
    if (flags & 128) != 0 {
      break
    }
  }
  match info {
    Some(info) =>
      (
        { info, blocks, seek_points, comments, cuesheet, cuesheets, pictures, },
        pos,
      )
    None => raise Invalid(4, "missing STREAMINFO")
  }
}

///|
/// Return all values of a tag name, comparing printable ASCII names without case.
pub fn VorbisComment::values(
  self : VorbisComment,
  name : String,
) -> Array[String] {
  let result = []
  for entry in self.entries {
    if entry.split_once("=") is Some((key, value)) {
      if key.to_string().to_lower() == name.to_lower() {
        result.push(value.to_string())
      }
    }
  }
  result
}
