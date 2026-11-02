"""Generate disposable FLAC CRC tables, preserving the frozen C7 source."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'_build/faster-than-libflac/candidate7-source'
TARGET=ROOT/'_build/faster-than-libflac/crc-table-source'
if not TARGET.exists():shutil.copytree(SOURCE,TARGET,ignore=shutil.ignore_patterns('_build','isolate_build'))
original=(SOURCE/'frame.mbt').read_text(encoding='utf-8')
def transition(state,byte,width):
 state ^= byte << (width-8)
 for _ in range(8):state=((state<<1)^((7 if width==8 else 0x8005) if state&(1<<(width-1)) else 0))&((1<<width)-1)
 return state
tables={width:[transition(0,b,width) for b in range(256)] for width in [8,16]}
def table_transition(state,byte,width):
 return tables[8][state^byte] if width==8 else ((state<<8)&65535)^tables[16][(state>>8)^byte]
for width in [8,16]:
 # Both transitions are GF(2)-linear, so equality on the state+byte basis
 # proves equality on every possible state and input byte.
 for state,byte in [(0,0)]+[(1<<i,0) for i in range(width)]+[(0,1<<i) for i in range(8)]:
  assert table_transition(state,byte,width)==transition(state,byte,width)
blocks=[]
for width in [8,16]:
 blocks+=['///|',f'// Generated MSB-first polynomial 0x{7 if width==8 else 0x8005:04x}, initial zero.',
          '// Private process-lifetime table; no writes or references escape this module.',
          f'let frame_crc{width}_table : FixedArray[Int] = [']
 for offset in range(0,256,16):blocks.append('  '+', '.join(str(x) for x in tables[width][offset:offset+16])+',')
 blocks+= [']','']
blocks+=['///|','// Width is 8 or 16 at all private callers. Checked data indexing retains',
         '// the original slice-bound failure behavior; an empty/reversed range is 0.',
         'fn frame_crc(data : Bytes, start : Int, end : Int, width : Int) -> Int {',
         '  let mut crc = 0','  if width == 8 {',
         '    for i = start; i < end; i = i+1 {',
         '      crc = frame_crc8_table.unsafe_get(crc ^ data[i].to_int())','    }',
         '  } else {','    for i = start; i < end; i = i+1 {',
         '      let index = (crc >> 8) ^ data[i].to_int()',
         '      crc = ((crc << 8) & 65535) ^ frame_crc16_table.unsafe_get(index)',
         '    }','  }','  crc','}']
start=original.index('///|\nfn frame_crc(');end=original.index('\n///|',start+5)
new=original[:start]+'\n'.join(blocks)+'\n'+original[end:]
(TARGET/'frame.mbt').write_text(new,encoding='utf-8')
report={'source':'_build/faster-than-libflac/candidate7-source/frame.mbt','target':str((TARGET/'frame.mbt').relative_to(ROOT)),
 'original_sha256':hashlib.sha256((SOURCE/'frame.mbt').read_bytes()).hexdigest(),'new_sha256':hashlib.sha256((TARGET/'frame.mbt').read_bytes()).hexdigest(),
 'polynomials':{'8':'0x07','16':'0x8005'},'bit_order':'MSB first','initial':0,'table_entries_each':256,
 'proof':'Both bit transition and table transition are GF(2)-linear; equal on all 16/24 state+input basis vectors and zero.',
 'production_changed':False,'performance_measured':False}
(ROOT/'validation/evidence/faster-than-libflac-crc-table-generation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
