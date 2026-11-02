"""Disposable fixed-block MD5 feeder and independent all-alignment oracle."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'_build/faster-than-libflac/md5-feed-source/md5.mbt'
OLD=ROOT/'validation/baselines/faster-than-libflac-md5-prefeed.mbt.txt'
if not OLD.exists(): OLD.write_bytes(TARGET.read_bytes())
text=OLD.read_text(encoding='utf-8')
text=text.replace('pending : Array[Byte]','pending : FixedArray[Byte]\n  mut used : Int')
text=text.replace('pending: [],','pending: FixedArray::make(64, 0),\n    used: 0,')
text=text.replace('bytes : Array[Byte]) -> Unit','bytes : FixedArray[Byte]) -> Unit')
begin=text.index('///|\nfn Md5::update')
digest=text[text.index('///|\n/// Finalization'):text.index('///|\nfn md5_update_frame')]
digest=digest.replace('pending: self.pending.copy(),','pending: self.pending.copy(),\n    used: self.used,')
digest=digest.replace('self.pending.length()','self.used')
update='''///|
/// Bulk-copy input into one fixed 64-byte block. used is always in 0..63 on
/// entry/exit; only a fully initialized 64-byte block reaches compression.
fn Md5::update(self : Md5, bytes : Bytes) -> Unit {
  self.length += bytes.length().to_int64()
  let mut cursor = 0
  while cursor < bytes.length() {
    let room = 64-self.used
    let remaining = bytes.length()-cursor
    let count = if remaining < room { remaining } else { room }
    self.pending.blit_from_bytes(self.used,bytes,cursor,count)
    self.used += count
    cursor += count
    if self.used == 64 { self.block(self.pending); self.used = 0 }
  }
}

'''
lines=['///|','/// Width-specialized signed little-endian stores preserve arbitrary prior',
       '/// update alignment. The rare crossing path works for every width, including',
       '/// 24-bit PCM and a nonaligned prefix before 16/32-bit PCM.',
       'fn md5_update_frame(state : Md5, frame : Frame) -> Unit {',
       '  let width = (frame.bits_per_sample+7)/8',
       '  state.length += (frame.block_size*frame.channels.length()*width).to_int64()',
       '  match width {']
for width in range(1,5):
 lines += [f'    {width} => {{','      for i in 0..<frame.block_size {','        for channel in frame.channels {','          let sample = channel[i]','          let used = state.used']
 if width>1:lines += [f'          if used <= {64-width} {{']
 for byte in range(width):lines += [f'            state.pending.unsafe_set(used+{byte}, ((sample >> {byte*8}) & 255).to_byte())']
 lines += [f'            state.used = used+{width}','            if state.used == 64 { state.block(state.pending); state.used = 0 }']
 if width>1:
  lines += ['          } else {',f'            for byte in 0..<{width} {{','              state.pending.unsafe_set(state.used, ((sample >> (byte*8)) & 255).to_byte())','              state.used += 1','              if state.used == 64 { state.block(state.pending); state.used = 0 }','            }','          }']
 lines += ['        }','      }','    }']
lines += ['    _ => abort("invalid internal MD5 PCM byte width")','  }','}']
TARGET.write_text(text[:begin]+update+digest+'\n'.join(lines)+'\n',encoding='utf-8')
packing_test=TARGET.parent/'md5_pcm_wbtest.mbt'
packing_archive=ROOT/'validation/baselines/faster-than-libflac-md5-prefeed-pcm-test.mbt.txt'
if not packing_archive.exists(): packing_archive.write_bytes(packing_test.read_bytes())
packing_text=packing_archive.read_text(encoding='utf-8')
assert packing_text.count('.pending.length()') == 3
packing_test.write_text(packing_text.replace('a.pending.length()', 'a.used').replace('b.pending.length()', 'b.used'),encoding='utf-8')
fixture=runpy.run_path(str(ROOT/'scripts/generate_md5_pcm_fixture.py'))
def pcm(bits,channels,count):
 return b''.join(fixture['sample'](bits,c,i,0).to_bytes((bits+7)//8,'little',signed=True) for i in range(count) for c in range(channels))
expected=[]
for prefix in range(64):
 transcript=hashlib.md5()
 for bits in range(4,33):
  for channels in range(1,9):
   state=hashlib.md5(bytes((i*13+prefix)%256 for i in range(prefix)))
   state.update(pcm(bits,channels,5));transcript.update(state.digest())
   state.update(bytes(range(7)))
   state.update(pcm(36-bits,channels%8+1,3));transcript.update(state.digest())
 expected.append('  b"'+''.join(f'\\x{b:02x}' for b in transcript.digest())+'",')
test='''// Generated independent Python hashlib alignment transcript expectations.
///|
let md5_feed_expected : Array[Bytes] = [
'''+ '\n'.join(expected)+'''
]
///|
test "MD5 fixed feed all 64 alignments 232 formats changes and digest continue" {
  for prefix in 0..<64 {
    let transcript = Md5::new()
    for bits in 4..<=32 {
      for channels in 1..<=8 {
        let state = Md5::new()
        state.update(Bytes::makei(prefix,i => ((i*13+prefix)%256).to_byte()))
        md5_update_frame(state,md5_pcm_fixture_frame(bits,channels,0,5,0))
        let first = state.digest()
        transcript.update(first)
        assert_eq(state.digest(),first)
        state.update(b"\\x00\\x01\\x02\\x03\\x04\\x05\\x06")
        md5_update_frame(state,md5_pcm_fixture_frame(36-bits,channels%8+1,0,3,0))
        transcript.update(state.digest())
        assert_true(state.used >= 0 && state.used < 64)
      }
    }
    assert_eq(transcript.digest(),md5_feed_expected[prefix])
  }
}
'''
(TARGET.parent/'md5_feed_wbtest.mbt').write_text(test,encoding='utf-8')
report={'old_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),'oracle_cases':64*29*8,'oracle_snapshots':2*64*29*8,'production_changed':False,'performance_measured':False}
(ROOT/'validation/evidence/faster-than-libflac-md5-feed-generation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
