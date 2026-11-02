#!/usr/bin/env python3
"""MoonFLAC encoder acceptance: original PCM -> MoonBit -> independent libFLAC."""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import math
import platform
from pathlib import Path
import random
import re
import struct
import subprocess
import time
from validate import ROOT, CACHE, LibFLAC, library, packed

WORK = CACHE / "encoder"
MANIFEST = WORK / "manifest.json"
EVIDENCE = ROOT / "validation/evidence"


def version(ref):
    return ctypes.c_char_p.in_dll(ref.dll, "FLAC__VERSION_STRING").value.decode()


def pcm_source(bits, channels, count, kind):
    rng = random.Random(9639 + bits * 11 + channels)
    lo, hi = -(1 << (bits-1)), (1 << (bits-1))-1
    edges = [lo, hi, 0, -1, 1, lo+1, hi-1]
    values = []
    for i in range(count):
        for c in range(channels):
            if kind == "matrix":
                value = (edges[(i+c)%7] if i<32 else int(math.sin((i+c*7)/11)*hi*.8) if i<192 else rng.randint(lo,hi))
            elif kind == "constant": value = hi//3
            elif kind == "silence": value = 0
            elif kind == "ramp": value = ((i+c*11)%512)-256
            elif kind == "quadratic": value = ((i%64)-32)**2
            elif kind == "cubic": value = ((i%32)-16)**3
            elif kind == "quartic": value = ((i%16)-8)**4
            elif kind == "impulse": value = hi if i%1024==0 else 0
            elif kind == "extrema": value = edges[(i+c)%7]
            elif kind == "alternating": value = hi if (i+c)%2 else lo
            elif kind == "wasted": value = (int(math.sin((i+c)/23)*hi*.3)//256)*256
            elif kind == "noise": value = rng.randint(lo,hi)
            elif kind == "ar": value = int((math.sin(i*.13)+.3*math.sin(i*.027+c*.02))*hi*.6)
            elif kind == "stereo-left": value = int(math.sin(i/23)*hi*.7) + (rng.randint(-2,2) if c else 0)
            elif kind == "stereo-right": value = int(math.sin(i/23)*hi*.7) + (rng.randint(-2,2) if not c else 0)
            else: raise ValueError(kind)
            values.append(min(hi,max(lo,value)))
    return values


def prepare(ref):
    WORK.mkdir(parents=True,exist_ok=True)
    cases=[]
    def add(name, pcm, bits, channels, rate=44100, block=256, effort=5, variable=False, mask=None, source="deterministic original PCM"):
        path=WORK/(name+".raw")
        raw=packed(pcm,bits)
        path.write_bytes(raw)
        case=dict(name=name,path=str(path.relative_to(ROOT)),bits=bits,channels=channels,rate=rate,block=block,effort=effort,
                  variable=variable,mask=mask,samples=len(pcm)//channels,pcm_sha256=hashlib.sha256(raw).hexdigest(),source=source)
        cases.append(case)
    for bits in range(4,33):
        for channels in range(1,9):
            add(f"matrix-{bits:02}-{channels}",pcm_source(bits,channels,257,"matrix"),bits,channels)
    for rate in (0,1,65535,655350,1048575):
        add(f"rate-{rate}",pcm_source(24,2,257,"matrix"),24,2,rate=rate)
    for block in (16,192,4096,65535):
        add(f"block-{block}",pcm_source(24,2,block+3,"ar"),24,2,block=block)
    for effort in range(9):
        for variable in (False,True):
            add(f"effort-{effort}-{'variable' if variable else 'fixed'}",pcm_source(32,2,769,"extrema"),32,2,block=256,effort=effort,variable=variable)
    for kind in ("silence","constant","ramp","quadratic","cubic","quartic","impulse","extrema","alternating","wasted","noise","ar","stereo-left","stereo-right"):
        for bits in (16,24,32):
            add(f"signal-{kind}-{bits}",pcm_source(bits,2,4099,kind),bits,2,block=1024,effort=8)
    for mask in (0,1,3,0x60f):
        add(f"mask-{mask:x}",pcm_source(24,6,257,"matrix"),24,6,mask=mask)
    # Distinct real recording formats; take explicitly documented first8192samples.
    for number in (1,22,28,38,39,40,41,42,43,60):
        source=next((CACHE/"flac-test-files/subset").glob(f"{number:02} - *.flac"))
        (channels,bits,rate),pcm=ref.decode(source)
        pcm=pcm[:8192*channels]
        add(f"real-{number:02}",pcm,bits,channels,rate,1024,8,source=f"libFLAC{version(ref)} decoded {source.relative_to(ROOT)}; first8192samples or source length")
    # Changing-property recordings become separate homogeneous encoder inputs.
    for number in (1,2,3,4):
        source=next((CACHE/"flac-test-files/uncommon").glob(f"{number:02} - *.flac"))
        framed,_=ref.decode(source,framed=True)
        position=0;segments=[]
        while position<len(framed):
            count,rate,bits,channels=struct.unpack_from("<IIII",framed,position);position+=16
            pcm=list(struct.unpack_from("<"+"i"*(count*channels),framed,position));position+=count*channels*4
            fmt=(bits,channels,rate)
            if not segments or segments[-1][0]!=fmt:segments.append((fmt,[]))
            if len(segments[-1][1])<8192*channels:
                segments[-1][1].extend(pcm[:8192*channels-len(segments[-1][1])])
        for index,((bits,channels,rate),pcm) in enumerate(segments):
            add(f"changing-{number}-{index}",pcm,bits,channels,rate,1024,8,source=f"libFLAC{version(ref)} decoded {source.relative_to(ROOT)}; homogeneous segment{index}; first8192samples")
    MANIFEST.write_text(json.dumps(cases,indent=2)+"\n",encoding="utf-8")
    print(f"Prepared {len(cases)} cases; libFLAC {version(ref)}",flush=True)


def read_pcm(case):
    data=(ROOT/case["path"]).read_bytes()
    width=(case["bits"]+7)//8
    return [int.from_bytes(data[i:i+width],"little",signed=True) for i in range(0,len(data),width)]


def cli_command(cli,case,output,effort=None):
    args=[str(cli),"encode",str(ROOT/case["path"]),str(output),"--raw","--sample-rate",str(case["rate"]),
          "--channels",str(case["channels"]),"--bits",str(case["bits"]),"--block-size",str(case["block"]),
          "--effort",str(case["effort"] if effort is None else effort)]
    if case["variable"]: args.append("--variable-block")
    if case["rate"]==0: args.append("--non-audio")
    if case["mask"] is not None: args.extend(["--channel-mask",f"0x{case['mask']:x}"])
    return args


def inspect(flac,output):
    analysis=output.with_suffix(".ana")
    subprocess.run([str(flac),"-a","-f","-s","-o",str(analysis),str(output)],check=True,capture_output=True)
    text=analysis.read_text()
    features={key:sorted(set(re.findall(r"(?:^|\s)"+key+r"=([^\s]+)",text)))
              for key in ("channel_assignment","type","order","wasted_bits","residual_type","partition_order","qlp_coeff_precision","quantization_level")}
    features["escaped_partition"]=bool(re.search(r"parameter\[\d+\]=ESCAPE|raw_bits",text,re.I))
    return features


def masks(output):
    data=output.read_bytes(); pos=4; values=[]
    while pos<len(data):
        kind=data[pos]&127; last=data[pos]&128; size=int.from_bytes(data[pos+1:pos+4],"big"); pos+=4
        payload=data[pos:pos+size]; pos+=size
        if kind==4:
            n=int.from_bytes(payload[:4],"little"); cur=4+n
            count=int.from_bytes(payload[cur:cur+4],"little");cur+=4
            for _ in range(count):
                n=int.from_bytes(payload[cur:cur+4],"little");cur+=4
                entry=payload[cur:cur+n].decode();cur+=n
                if entry.upper().startswith("WAVEFORMATEXTENSIBLE_CHANNEL_MASK="): values.append(int(entry.split("=",1)[1],0))
        if last:break
    return values


def compare(ref,args):
    cases=json.loads(MANIFEST.read_text())
    if args.match: cases=[x for x in cases if args.match in x["name"]]
    outcomes=[]
    for case in cases:
        output=WORK/(case["name"]+".moon.flac")
        entry=dict(name=case["name"],format={k:case[k] for k in ("bits","channels","rate","samples","block","effort","variable","mask")})
        command=cli_command(args.cli.resolve(),case,output)
        try:
            start=time.perf_counter()
            proc=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=args.timeout)
            entry.update(seconds=time.perf_counter()-start,command=command)
            if proc.returncode: raise RuntimeError(f"exit{proc.returncode}: {proc.stdout}{proc.stderr}")
            props,actual=ref.decode(output)
            expected=read_pcm(case)
            if props!=(case["channels"],case["bits"],case["rate"]) or actual!=expected:
                raise AssertionError(f"PCM/format mismatch {props}")
            if case["mask"] is not None and masks(output)!=[case["mask"]]: raise AssertionError("channel mask not preserved")
            subprocess.run([str(args.flac),"-t","-s",str(output)],check=True,capture_output=True,timeout=args.timeout)
            entry.update(status="pass",encoded_bytes=output.stat().st_size,pcm_sha256=case["pcm_sha256"],features=inspect(args.flac,output))
            if args.ffmpeg and case["rate"]>0:
                raw=output.with_suffix(".ffmpeg.s32")
                process=subprocess.run([str(args.ffmpeg),"-v","error","-y","-i",str(output),"-c:a","pcm_s32le","-f","s32le",str(raw)],capture_output=True,timeout=args.timeout)
                if process.returncode: raise RuntimeError(process.stderr.decode(errors="replace"))
                data=raw.read_bytes()
                decoded=[x[0]>>(32-case["bits"]) for x in struct.iter_unpack("<i",data)]
                if decoded!=expected: raise AssertionError("FFmpeg PCM mismatch")
                entry["ffmpeg"]="exact PCM pass"
        except Exception as exc: entry.update(status="fail",error=str(exc))
        outcomes.append(entry)
        print(case["name"],entry["status"],entry.get("error",""),flush=True)
        args.report.write_text(json.dumps(dict(oracle=f"libFLAC{version(ref)}",cases=outcomes),indent=2)+"\n",encoding="utf-8")
    return all(x["status"]=="pass" for x in outcomes)


def cross_backend(ref,args):
    """Run real MoonBit encoders, independently decode every emitted bitstream."""
    package=ROOT/"validation/encoder"
    package.mkdir(parents=True,exist_ok=True)
    cases=json.loads(MANIFEST.read_text())
    names=[f"matrix-{b:02}-{c}" for b,c in [(4,1),(12,3),(20,5),(24,6),(32,8)]]+["rate-0","effort-8-variable","signal-ar-24","mask-0","mask-60f"]
    selected=[next(c for c in cases if c["name"]==name) for name in names]
    for bits in range(4,33):
        for channels in range(1,9):
            original=next(c for c in cases if c["name"]==f"matrix-{bits:02}-{channels}")
            selected.append(dict(original,name=f"full-{bits:02}-{channels}",samples=33,block=32,effort=5))
    source='''// Generated by scripts/validate_encoder.py cross; libFLAC checks stdout.
///|
fn dump(name : String, data : Bytes) -> Unit {
  let hex = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]
  let text = StringBuilder()
  for byte in data {
    text.write_string(hex[byte.to_int() >> 4])
    text.write_string(hex[byte.to_int() & 15])
  }
  println("ENCODED " + name + " " + text.to_string())
}
///|
fn stream(pcm : Array[Int], config : @flac.EncoderConfig, cut : Int) -> Bytes raise {
  let encoder = @flac.Encoder::new(config)
  let output = @buffer.Buffer()
  let mut pos = 0
  let mut ended = false
  while true {
    match encoder.next() {
      EncodedBytes(bytes) => output.write_bytes(bytes)
      EncoderDone(_) => break
      NeedPcm => {
        if pos == pcm.length() {
          if ended { fail("NeedPcm after finish") }
          encoder.finish()
          ended = true
        } else {
          let end = if cut < 0 { pos + 1 } else if pos < cut { cut } else { pcm.length() }
          let accepted = encoder.push(pcm[pos:end].to_owned())
          if accepted == 0 { fail("backpressure despite drained output") }
          pos += accepted
        }
      }
    }
  }
  output.to_bytes()
}
///|
fn run() -> Unit raise {
'''
    expected={}
    for index,case in enumerate(selected):
        pcm=read_pcm(case)
        if case["name"].startswith("full-"):
            pcm=pcm[:33*case["channels"]]
            rng=random.Random(19639+case["bits"]*8+case["channels"])
            for i in range(24*case["channels"],len(pcm)):
                pcm[i]=rng.randint(-(1<<(case["bits"]-1)),(1<<(case["bits"]-1))-1)
        fmt=f'{{ sample_rate: {case["rate"]}, channels: {case["channels"]}, bits_per_sample: {case["bits"]} }}'
        mask_arg='' if case["mask"] is None else f', channel_mask={case["mask"]}U'
        config=f'@flac.EncoderConfig::new({fmt}, block_size={case["block"]}, effort={case["effort"]}, variable_block={str(case["variable"]).lower()}, non_audio={str(case["rate"]==0).lower()}{mask_arg})'
        source+=f'  let pcm{index} : Array[Int] = {pcm}\n  let config{index} = {config}\n'
        source+=f'  dump("{case["name"]}", @flac.encode_pcm(pcm{index}, config{index}))\n'
        expected[case["name"]]=(case,pcm)
    # Partial interleaved groups and a short final block: 17stereo samples.
    pcm=pcm_source(32,2,17,"extrema")
    short=dict(name="short",bits=32,channels=2,rate=48000,samples=17,mask=None)
    source+=f'  let small : Array[Int] = {pcm}\n'
    source+='  let config = @flac.EncoderConfig::new({ sample_rate: 48000, channels: 2, bits_per_sample: 32 }, block_size=16, effort=8)\n'
    for cut in range(1,len(pcm)):
        name=f"stream-cut-{cut}"
        source+=f'  dump("{name}", stream(small, config, {cut}))\n'
        expected[name]=(short,pcm)
    source+='  dump("stream-bytewise", stream(small, config, -1))\n}\n///|\nfn main { try run() catch { error => println("ERROR \\{error}") } }\n'
    expected["stream-bytewise"]=(short,pcm)
    (package/"main.mbt").write_text(source,encoding="utf-8")
    (package/"moon.pkg").write_text('import { "0717lee/moonflac" @flac, "moonbitlang/core/buffer" }\npkgtype(kind: "executable")\n',encoding="utf-8")
    build=ROOT/"_build/encoder-validation"
    subprocess.run(["moon","fmt","validation/encoder","--target-dir",str(build/"fmt")],cwd=ROOT,check=True,capture_output=True)
    reports=[]
    for target in ("native","js","wasm-gc"):
        command=["moon","run","--target",target,"--target-dir",str(build/target),"validation/encoder"]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=300)
        (WORK/f"cross-{target}.log").write_text(run.stdout+run.stderr,encoding="utf-8")
        outcomes=[]
        try:
            if run.returncode or "ERROR " in run.stdout: raise RuntimeError(run.stdout[-2000:]+run.stderr[-2000:])
            streams={m.group(1):bytes.fromhex(m.group(2)) for m in re.finditer(r"^ENCODED (\S+) ([0-9a-f]+)$",run.stdout,re.M)}
            if set(streams)!=set(expected): raise AssertionError(f"Expected {len(expected)} outputs, got{len(streams)}")
            for name,data in streams.items():
                output=WORK/f"cross-{target}-{name}.flac";output.write_bytes(data)
                case,pcm=expected[name]
                props,actual=ref.decode(output)
                if props!=(case["channels"],case["bits"],case["rate"]) or actual!=pcm: raise AssertionError(name+" PCM mismatch")
                if case["mask"] is not None and masks(output)!=[case["mask"]]:raise AssertionError(name+" mask mismatch")
                outcomes.append(dict(name=name,status="pass",bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            reports.append(dict(target=target,status="pass",command=command,cases=outcomes))
        except Exception as exc: reports.append(dict(target=target,status="fail",command=command,error=str(exc),cases=outcomes))
        print(target,reports[-1]["status"],reports[-1].get("error",""),flush=True)
    (EVIDENCE/"encoder-backends.json").write_text(json.dumps(dict(oracle=f"libFLAC{version(ref)}",targets=reports),indent=2)+"\n",encoding="utf-8")
    return all(r["status"]=="pass" for r in reports)


def measured(command,timeout):
    import psutil
    start=time.perf_counter()
    proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    monitor=psutil.Process(proc.pid);peak=0;polls=0
    while proc.poll() is None:
        if time.perf_counter()-start>timeout:
            proc.kill();proc.communicate();raise TimeoutError(command)
        try:
            memory=monitor.memory_info()
            peak=max(peak,getattr(memory,"peak_wset",memory.rss));polls+=1
        except psutil.NoSuchProcess:pass
        time.sleep(.005)
    out,err=proc.communicate()
    if proc.returncode:raise RuntimeError(err.decode(errors="replace")+out.decode(errors="replace"))
    return dict(seconds=time.perf_counter()-start,peak_process_bytes=peak,memory_polls=polls)


def benchmark(ref,args):
    binary_sha256=hashlib.sha256(args.cli.read_bytes()).hexdigest()
    toolchain=subprocess.check_output(["moon","version"],cwd=ROOT,text=True).strip()
    cases=json.loads(MANIFEST.read_text())
    tasks=[]
    for kind,bits in [("ar",24),("noise",16)]:
        pcm=pcm_source(bits,2,144000,kind)
        tasks.append((f"three-second-{kind}",pcm,bits,"deterministic original PCM;48000Hz;3seconds"))
    original=next(c for c in cases if c["name"]=="real-01")
    segment=read_pcm(original)
    pcm=(segment*(288000//len(segment)+1))[:288000]
    tasks.append(("three-second-recording",pcm,16,"repeat independently decoded real01segment to144000stereo samples;48000Hz"))
    rows=[]
    for name,pcm,bits,description in tasks:
        source=WORK/("bench-"+name+".raw");source.write_bytes(packed(pcm,bits))
        case=dict(path=str(source.relative_to(ROOT)),bits=bits,channels=2,rate=48000,block=1024,variable=False,mask=None,effort=5)
        for effort in (0,5,8):
            for codec in ("moonflac","libflac"):
                output=WORK/f"bench-{name}-{codec}-{effort}.flac"
                if codec=="moonflac":command=cli_command(args.cli.resolve(),case,output,effort)
                else:command=[str(args.flac),f"-{effort}","-f","-s","--lax","--no-padding","--no-seektable","--force-raw-format",
                              "--endian=little","--sign=signed","--channels=2",f"--bps={bits}","--sample-rate=48000","--blocksize=1024","-o",str(output),str(source)]
                entry=dict(input=name,description=description,codec=codec,effort=effort,pcm_bytes=source.stat().st_size,command=command)
                try:
                    entry.update(measured(command,args.timeout))
                    props,actual=ref.decode(output)
                    if props!=(2,bits,48000) or actual!=pcm:raise AssertionError("benchmark PCM mismatch")
                    size=output.stat().st_size
                    entry.update(status="pass",encoded_bytes=size,ratio_to_pcm=size/source.stat().st_size,
                                 sample_frames_per_second=144000/entry["seconds"])
                except Exception as exc:entry.update(status="fail",error=str(exc))
                rows.append(entry);print(name,codec,effort,entry["status"],entry.get("seconds"),flush=True)
                (EVIDENCE/"encoder-benchmark.json").write_text(json.dumps(dict(platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),toolchain=toolchain,binary_sha256=binary_sha256,
                    reference=f"libFLAC{version(ref)}",measurement="walltime includes process startup and file IO; memory sampled every5ms (Windows peak working set, otherwise RSS); one measured run percase; PCM verification excluded",cases=rows),indent=2)+"\n",encoding="utf-8")
    return all(r["status"]=="pass" for r in rows)


def forced(ref,args):
    """Decode test-only forced writer outputs with external tools, never MoonFLAC."""
    text=args.log.read_text(encoding="utf-8",errors="replace")
    matches=list(re.finditer(r"ENCODER-FORCED (\S+) ([0-9a-fA-F]+) (\d+) (\d+) (\d+) ([\d,-]+)",text))
    if not matches:raise RuntimeError("No forced writer records found")
    outcomes=[]
    for match in matches:
        name,hexdata,channels,bits,rate,values=match.groups()
        expected=[int(x) for x in values.split(",")]
        output=WORK/f"forced-{name}.flac";output.write_bytes(bytes.fromhex(hexdata))
        entry=dict(name=name,channels=int(channels),bits=int(bits),rate=int(rate))
        try:
            props,actual=ref.decode(output)
            if props!=(int(channels),int(bits),int(rate)) or actual!=expected:raise AssertionError("independent PCM mismatch")
            entry.update(status="pass",features=inspect(args.flac,output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                         pcm_sha256=hashlib.sha256(packed(expected,int(bits))).hexdigest())
        except Exception as exc:entry.update(status="fail",error=str(exc))
        outcomes.append(entry);print(name,entry["status"],entry.get("error",""),flush=True)
    (EVIDENCE/"encoder-forced.json").write_text(json.dumps(dict(oracle=f"libFLAC{version(ref)}",source_log=str(args.log),cases=outcomes),indent=2)+"\n",encoding="utf-8")
    return all(r["status"]=="pass" for r in outcomes)


def reference_frames(ref, source, consume, lost_sync=False):
    """libFLAC callback oracle; at most one decoded frame is held in Python."""
    C=ctypes
    pointer=ref.fn("stream_decoder_new",C.c_void_p)()
    errors=[];callback_errors=[]
    WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.POINTER(C.POINTER(C.c_int32)),C.c_void_p)
    META=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_void_p)
    ERROR=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_void_p)
    @WRITE
    def write(decoder,frame,buffers,client):
        try:
            count=C.cast(frame,C.POINTER(C.c_uint))[0]
            channels=ref.fn("stream_decoder_get_channels",C.c_uint,C.c_void_p)(decoder)
            bits=ref.fn("stream_decoder_get_bits_per_sample",C.c_uint,C.c_void_p)(decoder)
            rate=ref.fn("stream_decoder_get_sample_rate",C.c_uint,C.c_void_p)(decoder)
            values=[buffers[c][i] for i in range(count) for c in range(channels)]
            width=(bits+7)//8
            if width in (1,2,4):
                raw=struct.pack("<"+{1:"b",2:"h",4:"i"}[width]*len(values),*values)
            else:raw=packed(values,bits)
            consume((channels,bits,rate),count,raw)
            return 0
        except Exception as exc:
            callback_errors.append(exc)
            return 1
    @META
    def metadata(*args):pass
    @ERROR
    def error(decoder,status,client):errors.append(status)
    try:
        ref.fn("stream_decoder_set_md5_checking",C.c_int,C.c_void_p,C.c_int)(pointer,1)
        status=ref.fn("stream_decoder_init_file",C.c_int,C.c_void_p,C.c_char_p,WRITE,META,ERROR,C.c_void_p)(pointer,str(source).encode(),write,metadata,error,None)
        if status:raise RuntimeError(f"reference init={status}")
        ok=ref.fn("stream_decoder_process_until_end_of_stream",C.c_int,C.c_void_p)(pointer)
        md5=ref.fn("stream_decoder_finish",C.c_int,C.c_void_p)(pointer)
        if callback_errors:raise callback_errors[0]
        if not ok or not md5 or errors!=([0] if lost_sync else []):
            raise RuntimeError(f"reference process={ok}, MD5={md5}, errors={errors}")
        return errors
    finally:ref.fn("stream_decoder_delete",None,C.c_void_p)(pointer)


def source_mask(source):
    """Read only the comment block; skip pictures/padding/application payloads."""
    with source.open("rb") as stream:
        if stream.read(4)!=b"fLaC":return None
        while True:
            header=stream.read(4)
            if len(header)!=4:raise ValueError("incomplete source metadata")
            size=int.from_bytes(header[1:4],"big")
            if header[0]&127==4:
                payload=stream.read(size)
                length=int.from_bytes(payload[:4],"little");pos=4+length
                count=int.from_bytes(payload[pos:pos+4],"little");pos+=4
                for _ in range(count):
                    length=int.from_bytes(payload[pos:pos+4],"little");pos+=4
                    field=payload[pos:pos+length];pos+=length
                    if field.upper().startswith(b"WAVEFORMATEXTENSIBLE_CHANNEL_MASK="):
                        return int(field.split(b"=",1)[1],0)
            else:stream.seek(size,1)
            if header[0]&128:return None


def file_sha256(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()


def full_corpus(ref,args):
    folder=CACHE/"encoder-full-corpus";folder.mkdir(parents=True,exist_ok=True)
    sources=sorted((CACHE/"flac-test-files/subset").glob("*.flac"))+sorted((CACHE/"flac-test-files/uncommon").glob("*.flac"))
    if len(sources)!=75:raise RuntimeError(f"Expected75valid sourcefiles, found{len(sources)}")
    report_path=EVIDENCE/"encoder-full-corpus.json"
    report=dict(oracle=f"libFLAC{version(ref)}",scope="all64subset+11uncommon; completePCM; property changes split intohomogeneous streams",binary_sha256=file_sha256(args.cli),
                command="python scripts/validate_encoder.py full-corpus --cli PATH --timeout 600",sources=[])
    for source in sources:
        name=source.parent.name+"-"+source.name[:2]
        entry=dict(source=str(source.relative_to(ROOT)),source_sha256=file_sha256(source),segments=[])
        segments=[];open_file=None
        try:
            mask=source_mask(source)
            def consume(fmt,count,raw):
                nonlocal open_file
                if not segments or segments[-1]["format"]!=fmt:
                    if open_file:open_file.close()
                    path=folder/f"{name}-{len(segments)}.raw"
                    open_file=path.open("wb")
                    segments.append(dict(format=fmt,path=path,samples=0,frames=0))
                open_file.write(raw)
                segments[-1]["samples"]+=count;segments[-1]["frames"]+=1
            entry["reference_sync_errors"]=reference_frames(ref,source,consume,lost_sync=name=="uncommon-11")
            if open_file:open_file.close();open_file=None
            if not segments:raise ValueError("source has no samples")
            for index,segment in enumerate(segments):
                channels,bits,rate=segment["format"]
                path=segment["path"]
                output=folder/f"{name}-{index}.flac"
                case=dict(path=str(path.relative_to(ROOT)),bits=bits,channels=channels,rate=rate,block=4096,effort=5,variable=False,mask=mask)
                command=cli_command(args.cli.resolve(),case,output)
                result=dict(index=index,channels=channels,bits=bits,rate=rate,samples=segment["samples"],source_frames=segment["frames"],channel_mask=mask,pcm_bytes=path.stat().st_size,pcm_sha256=file_sha256(path),command=command)
                start=time.perf_counter()
                process=subprocess.run(command,capture_output=True,timeout=args.timeout)
                result["encode_seconds"]=time.perf_counter()-start
                if process.returncode:raise RuntimeError(process.stderr.decode(errors="replace")+process.stdout.decode(errors="replace"))
                with path.open("rb") as expected:
                    actual_samples=0
                    def compare_frame(fmt,count,raw):
                        nonlocal actual_samples
                        if fmt!=segment["format"]:raise AssertionError(f"output format mismatch{fmt}")
                        if expected.read(len(raw))!=raw:raise AssertionError(f"PCM mismatch near sample{actual_samples}")
                        actual_samples+=count
                    reference_frames(ref,output,compare_frame)
                    if expected.read(1) or actual_samples!=segment["samples"]:raise AssertionError("PCM length mismatch")
                if mask is not None and masks(output)!=[mask]:raise AssertionError("source mask not preserved")
                subprocess.run([str(args.flac),"-t","-s",str(output)],capture_output=True,check=True,timeout=args.timeout)
                result.update(status="pass",encoded_bytes=output.stat().st_size,encoded_sha256=file_sha256(output))
                entry["segments"].append(result)
            entry["status"]="pass"
        except Exception as exc:entry.update(status="fail",error=str(exc))
        finally:
            if open_file:open_file.close()
        report["sources"].append(entry)
        report["completed_sources"]=len(report["sources"])
        report["completed_streams"]=sum(len(x["segments"]) for x in report["sources"])
        report["status"]="running"
        report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(name,entry["status"],f"streams={len(entry['segments'])}",entry.get("error",""),flush=True)
    success=all(x["status"]=="pass" for x in report["sources"]) and report["completed_streams"]==84
    report["status"]="pass" if success else "fail"
    report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return success


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["prepare","compare","cross","benchmark","forced","full-corpus"])
    p.add_argument("--cli",type=Path)
    p.add_argument("--libflac")
    p.add_argument("--flac",type=Path,default=CACHE/"libflac/flac-1.5.0-win/Win64/flac.exe")
    p.add_argument("--ffmpeg",type=Path)
    p.add_argument("--match",default="")
    p.add_argument("--log",type=Path)
    p.add_argument("--timeout",type=int,default=120)
    p.add_argument("--report",type=Path,default=EVIDENCE/"encoder-native.json")
    args=p.parse_args()
    ref=LibFLAC(library(args.libflac))
    if args.action=="prepare":prepare(ref);return
    if args.action=="cross":raise SystemExit(0 if cross_backend(ref,args) else 1)
    if args.action=="forced":
        if not args.log:p.error("forced requires --log")
        raise SystemExit(0 if forced(ref,args) else 1)
    if not args.cli:p.error("compare requires --cli")
    if args.action=="full-corpus":raise SystemExit(0 if full_corpus(ref,args) else 1)
    if args.action=="benchmark":raise SystemExit(0 if benchmark(ref,args) else 1)
    raise SystemExit(0 if compare(ref,args) else 1)


if __name__=="__main__":main()
