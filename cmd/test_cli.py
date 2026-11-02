"""Executable CLI contracts, using independently generated PCM and libFLAC.

python cmd/test_cli.py --cli PATH --flac PATH
All artifacts live in a temporary directory and are removed after the run.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile


def extensible_wave(channels, mask, samples=32, depth=24):
    """Independent integer WAVE_FORMAT_EXTENSIBLE fixture generator."""
    width = depth // 8
    pcm = b"".join(((i * 7919 + channel * 101) % (1 << depth) - (1 << (depth-1))).to_bytes(width, "little", signed=True)
                   for i in range(samples) for channel in range(channels))
    fmt = struct.pack("<HHIIHHHHI", 0xfffe, channels, 48000, 48000 * channels * width,
                      channels * width, depth, 22, depth, mask)
    fmt += bytes.fromhex("0100000000001000800000aa00389b71")
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def wav_chunks(data):
    chunks, offset = {}, 12
    while offset + 8 <= len(data):
        tag, size = data[offset:offset + 4], struct.unpack_from("<I", data, offset + 4)[0]
        if size == 0xffffffff and tag == b"data":
            size = struct.unpack_from("<Q", chunks[b"ds64"], 8)[0]
        chunks[tag] = data[offset + 8:offset + 8 + size]
        offset += 8 + size + (size & 1)
    return chunks


def wav_mask(data):
    fmt = wav_chunks(data)[b"fmt "]
    return struct.unpack_from("<I", fmt, 20)[0] if struct.unpack_from("<H", fmt)[0] == 0xfffe else None


def generate_layout_fixtures(directory, flac):
    """Reusable fixtures for CLI and browser integration, encoded by libFLAC."""
    directory.mkdir(parents=True, exist_ok=True)
    cases = [("side51", 6, 0x060f), ("undefined4", 4, 0), ("partial4", 4, 3),
             ("default51", 6, 0x003f), ("stereo16", 2, 0x30)]
    for name, channels, mask in cases:
        wav = directory / f"{name}.wav"
        encoded = directory / f"{name}.flac"
        wav.write_bytes(extensible_wave(channels, mask, depth=16 if name == "stereo16" else 24))
        subprocess.run([flac, "-f", "--silent", "-o", str(encoded), str(wav)], check=True, capture_output=True)
        if mask == 0:
            # libFLAC drops a zero WAV mask on encode. Supply the explicit FLAC
            # convention separately to distinguish unspecified from absent.
            raw = directory / f"{name}.raw"
            raw.write_bytes(wav_chunks(wav.read_bytes())[b"data"])
            subprocess.run([flac, "-f", "--silent", "--force-raw-format", "--endian=little",
                            "--sign=signed", f"--channels={channels}", "--bps=24", "--sample-rate=48000",
                            "--tag=WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x0", "-o", str(encoded), str(raw)],
                           check=True, capture_output=True)
        subprocess.run([flac, "-d", "-f", "--silent", "-o",
                        str(directory / f"{name}-reference.wav"), str(encoded)], check=True, capture_output=True)
    # Raw input allows exact field spelling without an encoder-injected second tag.
    pcm = wav_chunks((directory / "side51.wav").read_bytes())[b"data"]
    raw = directory / "six.raw"
    raw.write_bytes(pcm)
    variants = [("mixedcase", "wAvEfOrMaTeXtEnSiBlE_cHaNnEl_MaSk=0x060f"),
                ("explicitdefault", "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x003f"), ("absent", None)]
    for index, (name, tag) in enumerate(variants):
        base = [flac, "-f", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
                "--channels=6", "--bps=24", "--sample-rate=48000"]
        if tag:
            base += ["--tag", tag]
        subprocess.run(base + ["-o", str(directory / f"{name}.flac"), str(raw)], check=True, capture_output=True)
        subprocess.run(base + ["--ogg", f"--serial-number={501 + index}", "-o",
                              str(directory / f"{name}.oga"), str(raw)], check=True, capture_output=True)
    (directory / "compatible.oga").write_bytes((directory / "absent.oga").read_bytes() + (directory / "explicitdefault.oga").read_bytes())
    (directory / "incompatible.oga").write_bytes((directory / "absent.oga").read_bytes() + (directory / "mixedcase.oga").read_bytes())
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--flac", required=True, type=Path)
    parser.add_argument("--layout-fixtures", type=Path)
    args = parser.parse_args()
    cli, flac = str(args.cli.resolve()), str(args.flac.resolve())
    checks = []

    def run(*command, code=0):
        result = subprocess.run(command, capture_output=True)
        assert result.returncode == code, (command, result.returncode, result.stderr)
        return result.stdout

    with tempfile.TemporaryDirectory(prefix="moonflac-cli-") as directory:
        work = Path(directory)
        for depth in (8, 16, 24, 32):
            width = depth // 8
            # Deterministic independent source, with full signed extremes.
            values = [-(1 << (depth - 1)), (1 << (depth - 1)) - 1, 0, -1, 1]
            values += [((i * 7919) % (1 << depth)) - (1 << (depth - 1)) for i in range(5001)]
            raw = b"".join(x.to_bytes(width, "little", signed=True) for x in values)
            source = work / f"音频-{depth}.raw"
            source.write_bytes(raw)
            encoded = source.with_suffix(".flac")
            run(flac, "-f", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
                "--channels=2", f"--bps={depth}", "--sample-rate=48000", "-o", str(encoded), str(source))
            info = json.loads(run(cli, "verify", str(encoded), "--json"))
            assert info["samples"] == len(values) // 2 and info["integrity"] == "Md5Verified", info
            run(cli, "verify", str(encoded), "--max-buffer", "4", code=3)
            run(cli, "verify", str(encoded), "--max-buffer", "1048576")
            output = work / "decoded.raw"
            run(cli, "decode", str(encoded), str(output), "--raw")
            assert output.read_bytes() == raw
            run(cli, "decode", str(encoded), str(output), "--raw", "--start", "7", "--end", "1003")
            assert output.read_bytes() == raw[7 * 2 * width:1003 * 2 * width]
            wav = work / "decoded.wav"
            run(cli, "decode", str(encoded), str(wav))
            roundtrip = work / "roundtrip.flac"
            run(flac, "-f", "--silent", "-o", str(roundtrip), str(wav))
            reference = work / "reference.raw"
            run(flac, "-d", "-f", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
                "-o", str(reference), str(roundtrip))
            assert reference.read_bytes() == raw
            run(cli, "decode", str(encoded), str(wav), "--rf64")
            rf64 = wav.read_bytes()
            assert rf64[:4] == b"RF64" and rf64[12:16] == b"ds64"
            assert struct.unpack_from("<Q", rf64, 28)[0] == len(raw)
            run(flac, "-f", "--silent", "-o", str(roundtrip), str(wav))
            broken = work / "truncated.flac"
            broken.write_bytes(encoded.read_bytes()[:-1])
            run(cli, "verify", str(broken), code=3)
            run(cli, "decode", str(encoded), str(encoded), code=2)
            alias = encoded.parent / "." / encoded.name
            run(cli, "decode", str(encoded), str(alias), code=2)
            hardlink = work / "same-file.flac"
            os.link(encoded, hardlink)
            run(cli, "decode", str(encoded), str(hardlink), code=2)
            hardlink.unlink()
            assert encoded.read_bytes()[:4] == b"fLaC"
            run(cli, "decode", str(encoded), str(output), "--start", "999999", code=2)
            run(cli, "decode", str(encoded), str(work / "absent" / "output.wav"), code=4)
            ogg_parts = []
            for serial in (101, 102):
                ogg = work / f"part-{serial}.oga"
                run(flac, "-f", "--silent", "--ogg", f"--serial-number={serial}", "--force-raw-format",
                    "--endian=little", "--sign=signed", "--channels=2", f"--bps={depth}",
                    "--sample-rate=48000", "-o", str(ogg), str(source))
                ogg_parts.append(ogg.read_bytes())
            chain = work / "chain.oga"
            chain.write_bytes(b"".join(ogg_parts))
            info = json.loads(run(cli, "verify", str(chain), "--json"))
            assert info["links"] == 2 and info["samples"] == len(values), info
            run(cli, "decode", str(chain), str(output), "--raw")
            assert output.read_bytes() == raw + raw
            run(cli, "decode", str(chain), str(wav))
            assert wav.read_bytes()[:4] == b"RF64"
            run(flac, "-f", "--silent", "-o", str(roundtrip), str(wav))
            run(flac, "-d", "-f", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
                "-o", str(reference), str(roundtrip))
            assert reference.read_bytes() == raw + raw
            boundary = len(values) // 2
            run(cli, "decode", str(chain), str(output), "--raw", "--start", str(boundary - 2),
                "--end", str(boundary + 3))
            assert output.read_bytes() == (raw + raw)[(boundary - 2) * width * 2:(boundary + 3) * width * 2]
            checks.append(f"{depth}-bit stereo: PCM, crop, WAV/libFLAC roundtrip, RF64, Ogg chain, truncation, same-path, range")
        mono = work / "odd.raw"
        mono.write_bytes(bytes([0, 127, 128, 255, 1]))
        mux_wav = work / "mux-source.wav"
        mux_wav.write_bytes(extensible_wave(2, 0x3, samples=5000, depth=16))
        mux_flac = work / "mux-source.flac"
        run(flac, "-f", "--silent", "-o", str(mux_flac), str(mux_wav))
        mux_ogg = work / "mux-output.oga"
        run(cli, "ogg", str(mux_flac), str(mux_ogg))
        mux_info = json.loads(run(cli, "verify", str(mux_ogg), "--json"))
        assert mux_info["samples"] == 5000 and mux_info["integrity"] == "Md5Verified", mux_info
        run(flac, "-t", str(mux_ogg))
        mux_raw = work / "mux-output.raw"
        run(flac, "-d", "-f", "--silent", "--force-raw-format", "--endian=little",
            "--sign=signed", "-o", str(mux_raw), str(mux_ogg))
        assert mux_raw.read_bytes() == wav_chunks(mux_wav.read_bytes())[b"data"]
        checks.append("Ogg mux: libFLAC accepts output and decoded PCM matches source")

        encoded = work / "odd.flac"
        run(flac, "-f", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
            "--channels=1", "--bps=8", "--sample-rate=8000", "-o", str(encoded), str(mono))
        run(cli, "decode", str(encoded), str(wav))
        odd_wav = wav.read_bytes()
        assert odd_wav[44:49] == bytes([128, 255, 0, 127, 129])
        assert odd_wav[49:] == bytes([0])
        assert struct.unpack_from("<I", odd_wav, 4)[0] == len(odd_wav) - 8
        checks.append("8-bit mono: unsigned WAV conversion, odd data pad, exact RIFF size")
        layout_dir = args.layout_fixtures or work / "layouts"
        cases = generate_layout_fixtures(layout_dir, flac)
        for name, channels, mask in cases + [("mixedcase", 6, 0x060f)]:
            encoded = layout_dir / f"{name}.flac"
            expected = wav_chunks((layout_dir / ("side51.wav" if name == "mixedcase" else f"{name}.wav")).read_bytes())[b"data"]
            for force_rf64 in (False, True):
                options = ["--rf64"] if force_rf64 else []
                run(cli, "decode", str(encoded), str(wav), *options)
                decoded = wav.read_bytes()
                assert wav_mask(decoded) == mask, (name, force_rf64, wav_mask(decoded), mask)
                assert wav_chunks(decoded)[b"data"] == expected
            if name != "mixedcase":
                reference_wav = (layout_dir / f"{name}-reference.wav").read_bytes()
                assert wav_chunks(reference_wav)[b"data"] == expected
                # libFLAC 1.5 converts explicit 0x0 to default4 0x33; MoonFLAC
                # intentionally preserves explicitly unspecified layout 0x0.
                if mask != 0:
                    assert wav_mask(reference_wav) == mask
        six_pcm = (layout_dir / "six.raw").read_bytes()
        compatible = layout_dir / "compatible.oga"
        run(cli, "decode", str(compatible), str(wav))
        assert wav_mask(wav.read_bytes()) == 0x3f
        assert wav_chunks(wav.read_bytes())[b"data"] == six_pcm + six_pcm
        run(cli, "decode", str(compatible), str(wav), "--start", "30", "--end", "35")
        assert wav_mask(wav.read_bytes()) == 0x3f
        assert wav_chunks(wav.read_bytes())[b"data"] == (six_pcm + six_pcm)[30*18:35*18]
        incompatible = layout_dir / "incompatible.oga"
        run(cli, "verify", str(incompatible))
        run(cli, "info", str(incompatible), "--json")
        run(cli, "decode", str(incompatible), str(output), "--raw")
        assert output.read_bytes() == six_pcm + six_pcm
        run(cli, "decode", str(incompatible), str(wav), code=3)
        run(cli, "decode", str(incompatible), str(wav), "--start", "30", "--end", "35", code=3)
        checks.append("channel layouts: side 5.1, partial mask, explicit zero, mixed-case tag, RF64, compatible/incompatible chains and cross-link crop")
        run(cli, "verify", str(work / "absent.flac"), code=4)
        run(cli, "decode", "input", "output", "--start", "9223372036854775808", code=2)
        run(cli, "decode", "input", "output", "--raw", "--rf64", code=2)
        run(cli, "verify", "input", "--max-buffer", "2147483648", code=2)
        run(cli, "verify", "input", "--max-buffer", "3", code=2)
        run(cli, "--help")
    print(json.dumps({"passed": checks, "exit_codes": [0, 2, 3, 4]}, indent=2))


if __name__ == "__main__":
    main()
