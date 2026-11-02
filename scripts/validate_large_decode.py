"""Complete the physical >4GiB stress with MoonFLAC RF64 output and disk PCM hash.

Run after stress_encoder.py long; the accepted source digest comes from actual
RF64 source generation and the independently verified libFLAC PCM stream.
"""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path
from stress_encoder import run, digest, version


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--long-report',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args()
    previous=json.loads(args.long_report.read_text())
    assert previous['status']=='passed'
    case=next(c for c in previous['results'] if c['source']['pcm_bytes']>2**32)
    cli=Path(previous['arguments']['cli'])
    assert digest(cli)==previous['cli_sha256']
    encoded=Path(case['encode']['command'][3])
    output=encoded.with_suffix('.decoded.rf64')
    result=run([str(cli),'decode',str(encoded),str(output),'--rf64'],28800)
    with output.open('rb') as stream:
        assert stream.read(12)==b'RF64\xff\xff\xff\xffWAVE'
        ds64=None
        fmt=None
        while True:
            head=stream.read(8)
            assert len(head)==8
            name,size=struct.unpack('<4sI',head)
            if name==b'data':
                assert size==0xffffffff and ds64 is not None and fmt is not None
                break
            assert size<=65536
            data=stream.read(size)
            if name==b'ds64':ds64=struct.unpack_from('<QQQ',data)
            if name==b'fmt ':fmt=data
            if size&1:stream.read(1)
        assert ds64==(output.stat().st_size-8,case['source']['pcm_bytes'],case['sample_frames'])
        tag,channels,rate=struct.unpack_from('<HHI',fmt)
        assert tag==0xfffe and channels==case['channels'] and rate==case['rate']
        assert struct.unpack_from('<H',fmt,18)[0]==case['bits']
        remaining=ds64[1]
        md5=hashlib.md5()
        while remaining:
            chunk=stream.read(min(1048576,remaining))
            assert chunk
            md5.update(chunk);remaining-=len(chunk)
        assert not stream.read(1)
    assert md5.hexdigest()==case['source']['pcm_md5']
    command=[args.ffmpeg,'-v','error','-i',str(encoded),'-map','0:a:0',
             '-c:a',f"pcm_s{case['bits']}le",'-f','md5','-']
    reference=subprocess.run(command,capture_output=True,text=True,check=True,timeout=600)
    assert reference.stdout.strip()=='MD5='+case['source']['pcm_md5'],reference.stdout
    args.report.write_text(json.dumps(dict(status='passed',cli_sha256=digest(cli),decode=result,
        output_path=str(output),physical_output_bytes=output.stat().st_size,ds64=list(ds64),pcm_md5=md5.hexdigest(),
        independent_expected_md5=case['independent']['libflac_decode']['stdout_pcm_md5'],
        ffmpeg=dict(version=version([args.ffmpeg,'-version']),command=command,pcm_md5=reference.stdout.strip())),indent=2)+'\n')
    print('Physical RF64 output and independently sourced PCM MD5 passed',ds64[1])
    # Retain this ignored cache artifact for independent physical inspection.


if __name__=='__main__':main()
