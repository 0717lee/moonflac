"""Paired release CLI benchmark with raw repetitions and independent PCM checks.

Runs sequentially on one pinned logical CPU, alternates codec order each round,
and records one warm-up plus five measurements. Do not run other heavy jobs.
Wall time includes process startup and I/O; profiler timings are separate.
"""
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
import wave
import urllib.request
from pathlib import Path

import psutil
from validate_encoder import LibFLAC, library, pcm_source, packed, version

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'validation/cache/hardening-benchmark'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(ref):
    WORK.mkdir(parents=True, exist_ok=True)
    cases = []
    for kind, bits, channels in [('noise',16,2), ('noise',32,2), ('ar',24,2),
                                  ('ar',32,2), ('ar',24,6)]:
        name = f'{kind}-{bits}-{channels}'
        path = WORK / (name+'.raw')
        path.write_bytes(packed(pcm_source(bits,channels,48000,kind),bits))
        cases.append(dict(name=name,path=str(path),bits=bits,channels=channels,rate=48000,
                          samples=48000,provenance='deterministic pcm_source seed 9639+bits*11+channels'))
    for number in [1,28,39,60]:
        source = next((ROOT/'validation/cache/flac-test-files/subset').glob(f'{number:02} - *.flac'))
        (channels,bits,rate),pcm = ref.decode(source)
        pcm = pcm[:rate*channels]  # contiguous original excerpt, never repeated
        path = WORK / f'recording-{number}.raw'
        path.write_bytes(packed(pcm,bits))
        cases.append(dict(name=f'recording-{number}',path=str(path),bits=bits,channels=channels,
                          rate=rate,samples=len(pcm)//channels,provenance=str(source.relative_to(ROOT)),
                          source_sha256=sha(source)))
    for case in cases:
        case['pcm_sha256']=sha(Path(case['path']))
    speech = WORK / 'speech.wav'
    if not speech.exists():
        url='https://download.pytorch.org/torchaudio/tutorial-assets/Lab41-SRI-VOiCES-src-sp0307-ch127535-sg0042.wav'
        with urllib.request.urlopen(url,timeout=60) as response:
            speech.write_bytes(response.read())
    assert sha(speech)=='c65fcd726d6b08c82c1e5dc7558f863cd8d483e3ed2f4a7bcf271dc1865ada14', 'speech fixture changed'
    if speech.exists():
        with wave.open(str(speech), 'rb') as wav:
            assert wav.getsampwidth() == 2
            raw = wav.readframes(wav.getnframes())
            path = WORK / 'speech.raw'
            path.write_bytes(raw)
            cases.append(dict(name='speech-voices', path=str(path), bits=16,
                channels=wav.getnchannels(), rate=wav.getframerate(), samples=wav.getnframes(),
                pcm_sha256=sha(path), source_sha256=sha(speech),
                provenance='https://download.pytorch.org/torchaudio/tutorial-assets/Lab41-SRI-VOiCES-src-sp0307-ch127535-sg0042.wav; complete utterance'))
    return cases


def measure(command):
    start=time.perf_counter()
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    monitored=psutil.Process(process.pid)
    peak=0
    while process.poll() is None:
        try:
            memory=monitored.memory_info()
            peak=max(peak,getattr(memory,'peak_wset',memory.rss))
        except psutil.NoSuchProcess:
            pass
        if time.perf_counter()-start>300:
            process.kill();process.communicate();raise TimeoutError(command)
        time.sleep(.002)
    stdout,stderr=process.communicate()
    if process.returncode:raise RuntimeError(stderr.decode(errors='replace')+stdout.decode(errors='replace'))
    return dict(seconds=time.perf_counter()-start,peak_process_bytes=peak)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',required=True,type=Path)
    p.add_argument('--candidate',required=True,type=Path)
    p.add_argument('--flac',type=Path,default=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
    p.add_argument('--libflac')
    p.add_argument('--report',type=Path,default=ROOT/'validation/evidence/hardening-benchmark.json')
    p.add_argument('--match',default='')
    p.add_argument('--core',action='store_true',help='paths refer to validation/benchmark executables; time encode_pcm only')
    args=p.parse_args()
    ref=LibFLAC(library(args.libflac))
    allowed=psutil.Process().cpu_affinity()
    cpu=allowed[len(allowed)//2]
    psutil.Process().cpu_affinity([cpu])  # inherited by all child executables
    binaries={k:v.resolve() for k,v in [('baseline',args.baseline),('candidate',args.candidate),('libflac',args.flac)]}
    report=dict(status='running',platform=platform.platform(),cpu=platform.processor(),logical_cpu=cpu,
                cpu_count=psutil.cpu_count(),physical_cpu_count=psutil.cpu_count(logical=False),
                reference=version(ref),toolchain=subprocess.check_output(['moon','version','--all'],text=True),
                binaries={k:dict(path=str(v),sha256=sha(v)) for k,v in binaries.items()},
                measurement='warm cache; pinned CPU; 1 warmup+5 measured; paired alternating order; process+IO wall time; 2ms memory polling; validation outside timing',
                cases=[])
    if args.core:
        report['measurement']='encode_pcm monotonic microseconds within a warm process; input unpacking and all file I/O excluded; 1 warmup+5 measured; pinned CPU'
        for case in inputs(ref):
            if args.match not in case['name']:continue
            for effort in [5,8]:
                entry=dict(case,effort=effort,runs={})
                for codec in ['baseline','candidate']:
                    output=WORK/f"core-{case['name']}-{effort}-{codec}.flac"
                    command=[str(binaries[codec]),case['path'],str(output),str(case['channels']),str(case['bits']),str(case['rate']),str(effort)]
                    result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=300)
                    times=[float(line.split()[2])/1e6 for line in result.stdout.splitlines() if line.startswith('CORE ')]
                    assert len(times)==6,result.stdout
                    props,pcm=ref.decode(output)
                    assert props==(case['channels'],case['bits'],case['rate'])
                    assert hashlib.sha256(packed(pcm,case['bits'])).hexdigest()==case['pcm_sha256']
                    median=statistics.median(times[1:])
                    entry['runs'][codec]=dict(warmup_seconds=times[0],seconds=times[1:],median_seconds=median,
                        mad_seconds=statistics.median(abs(t-median) for t in times[1:]),
                        encoded_sha256=sha(output),encoded_bytes=output.stat().st_size,independent_pcm='pass')
                entry['bitstream_unchanged']=entry['runs']['baseline']['encoded_sha256']==entry['runs']['candidate']['encoded_sha256']
                report['cases'].append(entry)
                args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                print(case['name'],effort,entry['runs'],flush=True)
        assert report['cases'], 'No benchmark inputs matched'
        report['status']='pass'
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return
    for case in inputs(ref):
        if args.match not in case['name']:continue
        for effort in [5,8]:
            entry=dict(case,effort=effort,block_size=1024,runs={k:[] for k in binaries})
            for repetition in range(6):
                order=list(binaries) if repetition%2==0 else list(reversed(binaries))
                for codec in order:
                    output=WORK/f"{case['name']}-{effort}-{codec}.flac"
                    if codec=='libflac':
                        command=[str(binaries[codec]),f'-{effort}','-f','-s','--lax','--no-padding','--no-seektable',
                                 '--force-raw-format','--endian=little','--sign=signed',f"--channels={case['channels']}",
                                 f"--bps={case['bits']}",f"--sample-rate={case['rate']}",'--blocksize=1024','-o',str(output),case['path']]
                    else:
                        command=[str(binaries[codec]),'encode',case['path'],str(output),'--raw','--sample-rate',str(case['rate']),
                                 '--channels',str(case['channels']),'--bits',str(case['bits']),'--block-size','1024','--effort',str(effort)]
                    load=psutil.cpu_percent(interval=.1,percpu=True)
                    run=measure(command)
                    run.update(repetition=repetition,warmup=repetition==0,host_cpu_before=load,
                               encoded_bytes=output.stat().st_size,encoded_sha256=sha(output))
                    props,pcm=ref.decode(output)
                    assert props==(case['channels'],case['bits'],case['rate'])
                    assert hashlib.sha256(packed(pcm,case['bits'])).hexdigest()==case['pcm_sha256']
                    subprocess.run([str(args.flac),'-t','-s',str(output)],check=True,capture_output=True)
                    run['independent_pcm_md5_crc']='pass'
                    entry['runs'][codec].append(run)
            entry['summary']={}
            for codec,runs in entry['runs'].items():
                times=[r['seconds'] for r in runs if not r['warmup']]
                median=statistics.median(times)
                entry['summary'][codec]=dict(median_seconds=median,min_seconds=min(times),max_seconds=max(times),
                    mad_seconds=statistics.median(abs(x-median) for x in times),sample_frames_per_second=case['samples']/median,
                    encoded_bytes=runs[-1]['encoded_bytes'],peak_process_bytes=max(r['peak_process_bytes'] for r in runs))
            entry['bitstream_unchanged']=entry['runs']['baseline'][-1]['encoded_sha256']==entry['runs']['candidate'][-1]['encoded_sha256']
            report['cases'].append(entry)
            args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(case['name'],effort,entry['summary'], 'same_bits',entry['bitstream_unchanged'],flush=True)
    assert report['cases'], 'No benchmark inputs matched'
    report['status']='pass'
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
