"""Long-stream native encoder memory evidence, with independent source MD5.

Uses/recreates the generated stereo24 tones from cmd/benchmark.py. This measures
one process per duration; effort defaults to zero for the buffering experiment.
Compression-quality/effort comparisons belong to scripts/validate_encoder.py.
"""
import argparse
import json
from pathlib import Path
import platform

from benchmark import measure, digest, checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--flac", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--durations", nargs="+", type=int, default=[5,60,300])
    parser.add_argument("--effort", type=int, default=0)
    parser.add_argument("--block-size", type=int, default=4096)
    parser.add_argument("--source-directory", type=Path, default=Path("validation/cache/benchmark"))
    parser.add_argument("--directory", type=Path, default=Path("validation/cache/encoder-memory"))
    args = parser.parse_args()
    cli, flac = str(args.cli.resolve()), str(args.flac.resolve())
    args.source_directory.mkdir(parents=True,exist_ok=True)
    args.directory.mkdir(parents=True,exist_ok=True)
    report = {"source":"Generated48kHz signed24 stereo amplitude0.6 tones440Hz/997Hz; not recordings",
              "method":"Single native release process per duration, full file encode+header finalization,5ms psutil polling/Windows peak_wset; reference flac-t and original PCM MD5 checked separately",
              "os":platform.platform(),"moon":checked(["moon","version"]),"compiler":checked(["moonc","-v"]),
              "cli_sha256":digest(Path(cli),"sha256"),"effort":args.effort,"block_size":args.block_size,"results":[]}
    for duration in args.durations:
        raw = args.source_directory/f"tones-{duration}s.raw"
        if not raw.exists():
            checked([args.ffmpeg,"-v","error","-y","-f","lavfi","-i",
                     "aevalsrc=0.6*sin(2*PI*440*t)|0.6*sin(2*PI*997*t):s=48000",
                     "-t",str(duration),"-c:a","pcm_s24le","-f","s24le",str(raw)])
        assert raw.stat().st_size == duration*48000*6
        original_md5 = digest(raw,"md5")
        output = args.directory/f"tones-{duration}s.flac"
        run = measure([cli,"encode",str(raw),str(output),"--raw","--sample-rate","48000",
                       "--channels","2","--bits","24","--effort",str(args.effort),"--block-size",str(args.block_size)])
        with output.open("rb") as stream:
            header = stream.read(42)
        assert header[:4] == b"fLaC" and header[26:42].hex() == original_md5
        assert int.from_bytes(header[18:26],"big") & ((1<<36)-1) == duration*48000
        checked([flac,"--silent","-t",str(output)])
        run.update(duration_seconds=duration,raw_bytes=raw.stat().st_size,encoded_bytes=output.stat().st_size,
                   source_pcm_md5=original_md5,audio_realtime_multiple=duration/run["seconds"])
        report["results"].append(run)
        (args.directory/"results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(run),flush=True)


if __name__ == "__main__":
    main()
