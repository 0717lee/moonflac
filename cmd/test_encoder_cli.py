"""Independent integer-PCM encoder CLI interoperability and malformed-input tests.

python cmd/test_encoder_cli.py --cli PATH --flac PATH
Source WAV/RF64 bytes and expected integer samples are made in Python; the
independent official libFLAC library/executable decodes MoonFLAC output for comparison.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from validate import LibFLAC, library, packed


def chunk(tag, data, sentinel=False):
    return tag + struct.pack("<I", 0xffffffff if sentinel else len(data)) + data + bytes(len(data) & 1)


def pcm_wave(bits, channels=2, container=32, mask=0, rf64=False, table=False):
    edges = [-(1 << (bits-1)), (1 << (bits-1))-1, -1, 0, 1]
    values = [edges[i % len(edges)] for i in range(37) for _ in range(channels)]
    width, shift = container // 8, container-bits
    pcm = b"".join(((value << shift) + (128 if container == 8 else 0)).to_bytes(width, "little", signed=container != 8) for value in values)
    fmt = struct.pack("<HHIIHHHHI", 65534, channels, 48000, 48000*channels*width,
                      channels*width, container, 22, bits, mask)
    fmt += bytes.fromhex("0100000000001000800000aa00389b71")
    unknown = chunk(b"JUNK", b"abc", sentinel=table) + chunk(b"JUNK", b"12345", sentinel=table)
    tail = unknown + chunk(b"fmt ", fmt) + chunk(b"data", pcm, sentinel=rf64)
    if rf64:
        records = b"JUNK" + struct.pack("<Q", 3) + b"JUNK" + struct.pack("<Q", 5) if table else b""
        ds64_length = 28+len(records)
        riff_size = 4+8+ds64_length+len(tail)
        ds64 = struct.pack("<QQQI", riff_size, len(pcm), len(values)//channels, 2 if table else 0)+records
        result = b"RF64\xff\xff\xff\xffWAVE"+chunk(b"ds64",ds64)+tail
    else:
        result = b"RIFF"+struct.pack("<I",len(tail)+4)+b"WAVE"+tail
    raw = b"".join(value.to_bytes((bits+7)//8,"little",signed=True) for value in values)
    return result, raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--flac", required=True, type=Path)
    parser.add_argument("--libflac", type=Path)
    args = parser.parse_args()
    cli, flac = str(args.cli.resolve()), str(args.flac.resolve())
    reference = LibFLAC(library(args.libflac))
    checks = []

    def run(*command, code=0):
        result = subprocess.run(command, capture_output=True)
        assert result.returncode == code, (command, result.returncode, result.stderr.decode(errors="replace"))
        return result.stdout

    with tempfile.TemporaryDirectory(prefix="moonflac-encoder-") as directory:
        work = Path(directory)
        source, encoded, decoded = work/"音频.wav", work/"encoded.flac", work/"decoded.raw"
        for bits in range(4,33):
            for rf64 in (False,True):
                wave, raw = pcm_wave(bits,container=8 if bits<=8 else 32,rf64=rf64,table=rf64)
                source.write_bytes(wave)
                run(cli,"encode",str(source),str(encoded),"--block-size","32","--effort","1")
                properties, samples = reference.decode(encoded)
                assert properties == (2,bits,48000),properties
                assert packed(samples,bits) == raw, (bits,rf64)
                info = json.loads(run(cli,"verify",str(encoded),"--json"))
                assert info["bits_per_sample"] == bits and info["samples"] == 37
                tags = info["metadata"]["comments"]["entries"]
                assert any(tag.upper().startswith("WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0X0") for tag in tags),tags
        checks.append("29 valid bit depths in RIFF and RF64, signed32 and unsigned8 containers, explicit mask0, repeated ds64 table IDs, odd unknown chunk padding")
        # Classic PCM fmt16, unsigned 8-bit, with an odd data pad.
        fmt = struct.pack("<HHIIHH",1,1,8000,8000,1,8)
        tail = chunk(b"fmt ",fmt)+chunk(b"data",bytes([0,127,128,255,1]))
        source.write_bytes(b"RIFF"+struct.pack("<I",len(tail)+4)+b"WAVE"+tail)
        run(cli,"encode",str(source),str(encoded))
        run(flac,"-d","-f","--silent","--force-raw-format","--endian=little","--sign=signed",
            "-o",str(decoded),str(encoded))
        assert decoded.read_bytes() == bytes([128,255,0,127,129])
        checks.append("classic PCM WAV with unsigned8 conversion and odd final data pad")
        valid, raw = pcm_wave(24,channels=6,container=24,mask=0x060f,rf64=True)
        source.write_bytes(valid)
        run(cli,"encode",str(source),str(encoded),"--variable-block","--effort","0")
        info = json.loads(run(cli,"info",str(encoded),"--json"))
        assert any("0x060f" in tag.lower() or "0x60f" in tag.lower() for tag in info["metadata"]["comments"]["entries"])
        rawfile = work/"raw.pcm"
        rawfile.write_bytes(raw)
        run(cli,"encode",str(rawfile),str(encoded),"--raw","--sample-rate","48000","--channels","6","--bits","24","--channel-mask","0x060f")
        run(flac,"-d","-f","--silent","--force-raw-format","--endian=little","--sign=signed",
            "-o",str(decoded),str(encoded))
        assert decoded.read_bytes() == raw
        checks.append("raw signed24 and RF64 side-5.1 layout, variable blocking")
        mutations = []
        short, _ = pcm_wave(24,container=32)
        mutations += [("truncated",short[:-1]),("trailing",short+b"x")]
        data_at = short.index(b"data")+8
        bad = bytearray(short); bad[data_at] |= 1; mutations.append(("nonzero low padding",bytes(bad)))
        fmt_at = short.index(b"fmt ")+8
        bad = bytearray(short); struct.pack_into("<H",bad,fmt_at,3); mutations.append(("float WAV",bytes(bad)))
        bad = bytearray(short); struct.pack_into("<H",bad,fmt_at+16,100); mutations.append(("fmt extension overflow",bytes(bad)))
        bad = bytearray(short); struct.pack_into("<I",bad,data_at-4,0xfffffff0); mutations.append(("chunk boundary overflow",bytes(bad)))
        bad = bytearray(valid); struct.pack_into("<Q",bad,36,999); mutations.append(("ds64 sample count",bytes(bad)))
        bad = bytearray(valid); struct.pack_into("<Q",bad,20,0xffffffffffffffff); mutations.append(("ds64 size overflow",bytes(bad)))
        for label, payload in mutations:
            source.write_bytes(payload)
            run(cli,"encode",str(source),str(encoded),code=3)
        for payload in [b"",b"\x0f\x00",b"\xff"]:
            rawfile.write_bytes(payload)
            run(cli,"encode",str(rawfile),str(encoded),"--raw","--sample-rate","48000","--channels","2","--bits","4",code=3)
        checks.append("reject float, bad valid-bit padding, truncated/raw partial sample, non-sign-extended raw, RIFF overflow/trailing data, ds64 overflow/mismatch")
        source.write_bytes(short)
        run(cli,"encode",str(source),str(source),code=2)
        alias = work/"alias.wav"; os.link(source,alias)
        run(cli,"encode",str(source),str(alias),code=2)
        run(cli,"encode",str(work/"missing.wav"),str(encoded),code=4)
        run(cli,"encode",str(source),str(work/"absent"/"out.flac"),code=4)
        run(cli,"encode",str(source),str(encoded),"--effort","9",code=2)
        run(cli,"encode",str(source),str(encoded),"--raw",code=2)
        run(cli,"encode",str(source),str(encoded),"--raw","--sample-rate","0","--channels","2","--bits","16",code=2)
        checks.append("same-path/hardlink protection and stable usage/input/output exit codes")
    print(json.dumps({"passed":checks},indent=2))


if __name__ == "__main__":
    main()
