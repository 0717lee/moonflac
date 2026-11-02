#!/usr/bin/env python3
"""Independent libFLAC oracle and MoonFLAC CLI acceptance runner (Python 3)."""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "validation/cache"
RESULTS = ROOT / "validation/results"

class LibFLAC:
    """ctypes is used only by this external reference tool, never by MoonFLAC."""
    def __init__(self, path):
        self.dll = C.CDLL(str(path))
    def fn(self, name, result, *args):
        f = getattr(self.dll, "FLAC__" + name)
        f.restype, f.argtypes = result, args
        return f
    def encode(self, output, pcm, channels, bits, rate, block=1024, ogg=False):
        p = self.fn("stream_encoder_new", C.c_void_p)()
        if not p: raise RuntimeError("libFLAC encoder allocation failed")
        try:
            for key, value in [("channels", channels), ("bits_per_sample", bits),
                               ("sample_rate", rate), ("compression_level", 8),
                               ("streamable_subset", 0), ("blocksize", block), ("verify", 1)]:
                if not self.fn("stream_encoder_set_" + key, C.c_int, C.c_void_p, C.c_uint)(p, value):
                    raise RuntimeError(f"libFLAC rejected {key}={value}")
            init = "stream_encoder_init_ogg_file" if ogg else "stream_encoder_init_file"
            status = self.fn(init, C.c_int, C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p)(p, os.fsencode(output), None, None)
            if status: raise RuntimeError(f"libFLAC init status {status}")
            data = (C.c_int32 * len(pcm))(*pcm)
            if not self.fn("stream_encoder_process_interleaved", C.c_int, C.c_void_p, C.POINTER(C.c_int32), C.c_uint)(p, data, len(pcm)//channels):
                raise RuntimeError("libFLAC encoding failed")
            if not self.fn("stream_encoder_finish", C.c_int, C.c_void_p)(p):
                raise RuntimeError("libFLAC finish failed")
        finally:
            self.fn("stream_encoder_delete", None, C.c_void_p)(p)
    def decode(self, source, framed=False, allow_lost_sync=False):
        p = self.fn("stream_decoder_new", C.c_void_p)()
        self.frame_positions = []
        samples, errors, props, records = [], [], [], []
        WRITE = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.POINTER(C.POINTER(C.c_int32)), C.c_void_p)
        META = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p)
        ERROR = C.CFUNCTYPE(None, C.c_void_p, C.c_int, C.c_void_p)
        @WRITE
        def write(dec, frame, buffers, client):
            n = C.cast(frame, C.POINTER(C.c_uint))[0]
            channels = self.fn("stream_decoder_get_channels", C.c_uint, C.c_void_p)(dec)
            bits = self.fn("stream_decoder_get_bits_per_sample", C.c_uint, C.c_void_p)(dec)
            rate = self.fn("stream_decoder_get_sample_rate", C.c_uint, C.c_void_p)(dec)
            props.append((channels, bits, rate))
            position = C.c_uint64()
            if self.fn("stream_decoder_get_decode_position", C.c_int, C.c_void_p, C.POINTER(C.c_uint64))(dec, C.byref(position)):
                self.frame_positions.append(position.value)
            values = [buffers[c][i] for i in range(n) for c in range(channels)]
            samples.extend(values)
            if framed:
                records.append(struct.pack("<IIII", n, rate, bits, channels) + struct.pack("<"+"i"*len(values), *values))
            return 0
        @META
        def meta(*args): pass
        @ERROR
        def error(dec, status, client): errors.append(status)
        try:
            self.fn("stream_decoder_set_md5_checking", C.c_int, C.c_void_p, C.c_int)(p, 1)
            init = "stream_decoder_init_ogg_file" if source.read_bytes()[:4] == b"OggS" else "stream_decoder_init_file"
            status = self.fn(init, C.c_int, C.c_void_p, C.c_char_p, WRITE, META, ERROR, C.c_void_p)(p, os.fsencode(source), write, meta, error, None)
            if status: raise RuntimeError(f"libFLAC decoder init {status}")
            ok = self.fn("stream_decoder_process_until_end_of_stream", C.c_int, C.c_void_p)(p)
            md5 = self.fn("stream_decoder_finish", C.c_int, C.c_void_p)(p)
            bad_errors = [x for x in errors if not (allow_lost_sync and x == 0)]
            if not ok or bad_errors or not md5: raise RuntimeError(f"libFLAC rejection: process={ok}, errors={errors}, md5={md5}")
            if not props: raise RuntimeError("No decoded frames")
            if framed: return b"".join(records), errors
            if len(set(props)) != 1: raise RuntimeError("Changing stream properties: per-frame comparison needed")
            return props[0], samples
        finally:
            self.fn("stream_decoder_delete", None, C.c_void_p)(p)

def library(value):
    if value: return Path(value).resolve()
    paths = list((CACHE / "libflac").glob("**/Win64/libFLAC.dll"))
    if paths: return paths[0]
    from ctypes.util import find_library
    found = find_library("FLAC")
    if found: return found
    raise SystemExit("libFLAC not found; run scripts/prepare-validation.ps1 or pass --libflac")

def packed(samples, bits):
    width = (bits + 7)//8
    return b"".join(int(x).to_bytes(width, "little", signed=True) for x in samples)

def signal(bits, channels, count=2117):
    rng = random.Random(9639 + bits * 8 + channels)
    lo, hi = -(1 << (bits-1)), (1 << (bits-1))-1
    edges = [lo, hi, 0, -1, 1, lo+1, hi-1]
    return [edges[(i+c)%len(edges)] if i < 128 else
            int(math.sin((i+c*17)/23.0)*hi*0.9) if i < 1500 else rng.randint(lo, hi)
            for i in range(count) for c in range(channels)]

def generate(ref):
    folder = CACHE / "generated"
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    settings = [(f"depth-{b:02}-channels-{c}", b, c, 44100, 1024, False) for b in range(4,33) for c in range(1,9)]
    settings += [(f"rate-{r}", 16, 2, r, 1024, False) for r in (1, 8000, 65535, 655350, 1048575)]
    settings += [(f"block-{n}", 24, 2, 48000, n, False) for n in (16, 192, 4096, 65535)]
    settings += [(f"ogg-{b}-{c}", b, c, 48000, 1024, True) for b,c in ((4,1),(16,2),(24,6),(32,8))]
    for name,bits,channels,rate,block,ogg in settings:
        output = folder / (name + (".oga" if ogg else ".flac"))
        pcm = signal(bits, channels, max(2117, block+3))
        ref.encode(output, pcm, channels, bits, rate, block, ogg)
        props, actual = ref.decode(output)
        if props != (channels,bits,rate) or actual != pcm: raise AssertionError(f"Independent generation verification failed: {name}")
        raw = output.with_suffix(".pcm")
        raw.write_bytes(packed(pcm,bits))
        cases.append(dict(path=str(output.relative_to(ROOT)), pcm=str(raw.relative_to(ROOT)), bits=bits, channels=channels, rate=rate, samples=len(pcm)//channels, sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
    (folder / "manifest.json").write_text(json.dumps(cases,indent=2)+"\n",encoding="utf-8")
    print(f"Generated and independently decoded {len(cases)} cases",flush=True)

def compare(ref, cli, paths, timeout, max_buffer=None, report=None):
    RESULTS.mkdir(parents=True,exist_ok=True)
    outcomes = []
    for index, source in enumerate(paths):
        entry = {"path":str(source.relative_to(ROOT))}
        try:
            (channels,bits,rate), pcm = ref.decode(source)
            expected = packed(pcm,bits)
            target = RESULTS / f"actual-{os.getpid()}.pcm"
            target.unlink(missing_ok=True)
            start=time.perf_counter()
            command=[str(cli),"decode",str(source),str(target),"--raw"]
            if max_buffer: command += ["--max-buffer",str(max_buffer)]
            proc=subprocess.run(command,capture_output=True,timeout=timeout)
            entry.update(seconds=time.perf_counter()-start,exit=proc.returncode,samples=len(pcm)//channels,bits=bits,channels=channels,rate=rate)
            if proc.returncode: raise AssertionError(proc.stderr.decode(errors="replace") or proc.stdout.decode(errors="replace"))
            actual=target.read_bytes()
            if actual != expected:
                first=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
                raise AssertionError(f"PCM differs at byte {first}; lengths actual={len(actual)}, reference={len(expected)}")
            entry.update(status="pass",sha256_pcm=hashlib.sha256(expected).hexdigest())
        except Exception as exc:
            entry.update(status="fail",error=str(exc))
        outcomes.append(entry)
        print(f"[{index+1}/{len(paths)}] {entry['status']}: {source.name}" + (f" {entry['error']}" if entry.get("error") else ""),flush=True)
        (report or RESULTS / "oracle.json").write_text(json.dumps(outcomes,indent=2)+"\n",encoding="utf-8")
    return not any(x["status"]!="pass" for x in outcomes)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["generate","compare","frames"])
    p.add_argument("--libflac")
    p.add_argument("--cli",type=Path)
    p.add_argument("--corpus",choices=["generated","subset","uncommon","all"],default="generated")
    p.add_argument("--match",default="")
    p.add_argument("--timeout",type=int,default=120)
    p.add_argument("--max-buffer",type=int)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    ref=LibFLAC(library(args.libflac))
    if args.action=="generate": generate(ref); return
    if not args.cli: p.error("compare needs --cli PATH")
    groups=[CACHE/"generated"] if args.corpus=="generated" else ([CACHE/"generated",CACHE/"flac-test-files/subset",CACHE/"flac-test-files/uncommon"] if args.corpus=="all" else [CACHE/"flac-test-files"/args.corpus])
    paths=sorted(x for folder in groups for x in folder.rglob("*") if x.suffix in (".flac",".oga") and args.match in str(x))
    if not paths: raise SystemExit("No inputs found")
    if args.action=="frames":
        outcomes=[]
        RESULTS.mkdir(parents=True,exist_ok=True)
        for source in paths:
            raw=source.read_bytes()[:4]!=b"fLaC" and source.suffix!=".oga"
            entry={"path":str(source.relative_to(ROOT)),"mode":"raw" if raw else "file"}
            try:
                expected, errors=ref.decode(source,framed=True,allow_lost_sync=raw)
                target=RESULTS/f"frames-{os.getpid()}.pcm"
                target.unlink(missing_ok=True)
                proc=subprocess.run([str(args.cli.resolve()),str(source),str(target),entry["mode"]],capture_output=True,timeout=args.timeout)
                if proc.returncode: raise AssertionError(proc.stdout.decode(errors="replace")+proc.stderr.decode(errors="replace"))
                actual=target.read_bytes()
                if actual!=expected: raise AssertionError(f"Frame PCM mismatch: {len(actual)} vs {len(expected)} bytes")
                entry.update(status="pass",sha256=hashlib.sha256(expected).hexdigest(),reference_sync_errors=errors,diagnostic=proc.stdout.decode(errors="replace"))
            except Exception as exc: entry.update(status="fail",error=str(exc))
            outcomes.append(entry)
            print(entry,flush=True)
            (RESULTS/"frames.json").write_text(json.dumps(outcomes,indent=2)+"\n")
        raise SystemExit(0 if all(x["status"]=="pass" for x in outcomes) else 1)
    raise SystemExit(0 if compare(ref,args.cli.resolve(),paths,args.timeout,args.max_buffer,args.report) else 1)
if __name__=="__main__": main()
