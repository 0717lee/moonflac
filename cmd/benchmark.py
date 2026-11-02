"""Reproducible streaming CLI throughput and process memory measurements.

Requires ffmpeg, libFLAC and Python psutil. Sources are generated integer PCM,
not recordings. All input/output artifacts are local in validation/cache/benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time

import psutil


def checked(command):
    result = subprocess.run(command, capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="replace").strip()


def measure(command):
    start = time.perf_counter()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = psutil.Process(child.pid)
    peak_rss = peak_os = polls = 0
    while child.poll() is None:
        try:
            memory = process.memory_info()
            peak_rss = max(peak_rss, memory.rss)
            peak_os = max(peak_os, getattr(memory, "peak_wset", memory.rss))
            polls += 1
        except psutil.NoSuchProcess:
            break
        time.sleep(0.005)
    stdout, stderr = child.communicate()
    elapsed = time.perf_counter() - start
    if child.returncode:
        raise RuntimeError((command, child.returncode, stderr.decode(errors="replace")))
    return {
        "seconds": elapsed,
        "sampled_peak_rss_bytes": peak_rss,
        "os_peak_working_set_bytes": peak_os,
        "memory_polls": polls,
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
    }


def digest(path, name):
    value = hashlib.new(name)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--flac", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--directory", type=Path, default=Path("validation/cache/benchmark"))
    parser.add_argument("--durations", type=int, nargs="+", default=[5, 60, 300])
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    cli, flac = str(args.cli.resolve()), str(args.flac.resolve())
    args.directory.mkdir(parents=True, exist_ok=True)
    cpu = platform.processor()
    if platform.system() == "Windows":
        cpu = checked(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
    report = {
        "environment": {
            "os": platform.platform(), "cpu": cpu, "python": platform.python_version(),
            "psutil": psutil.__version__, "moon": checked(["moon", "version"]),
            "compiler": checked(["moonc", "-v"]),
            "ffmpeg": checked([args.ffmpeg, "-version"]).splitlines()[0],
            "flac": checked([flac, "--version"]), "cli": cli,
            "cli_sha256": digest(Path(cli), "sha256"),
            "physical_memory_bytes": psutil.virtual_memory().total,
        },
        "source": {
            "description": "Generated stereo tones, left 440 Hz/right 997 Hz, amplitude 0.6, 48 kHz signed 24-bit little-endian PCM",
            "filter": "aevalsrc=0.6*sin(2*PI*440*t)|0.6*sin(2*PI*997*t):s=48000",
            "flac_options": "-8 --force-raw-format --endian=little --sign=signed --channels=2 --bps=24 --sample-rate=48000",
        },
        "method": "3 process runs per input by default; 5 ms psutil polling; Windows peak_wset is OS-maintained high-water mark; wall times include process startup and file I/O, warmed filesystem cache; no CPU affinity or power profile controls",
        "results": [],
    }
    for duration in args.durations:
        raw = args.directory / f"tones-{duration}s.raw"
        encoded = raw.with_suffix(".flac")
        checked([args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", report["source"]["filter"], "-t", str(duration), "-c:a", "pcm_s24le", "-f", "s24le", str(raw)])
        assert raw.stat().st_size == duration * 48000 * 2 * 3
        checked([flac, "-f", "--silent", "-8", "--force-raw-format", "--endian=little", "--sign=signed",
                 "--channels=2", "--bps=24", "--sample-rate=48000", "-o", str(encoded), str(raw)])
        raw_md5 = digest(raw, "md5")
        with encoded.open("rb") as stream:
            stream.seek(26)
            streaminfo_md5 = stream.read(16).hex()
        assert raw_md5 == streaminfo_md5
        row = {"duration_seconds": duration, "samples_per_channel": duration * 48000,
               "raw_bytes": raw.stat().st_size, "flac_bytes": encoded.stat().st_size,
               "source_pcm_md5": raw_md5, "flac_sha256": digest(encoded, "sha256"),
               "moonflac_runs": [], "libflac_runs": []}
        for _ in range(args.repeats):
            measured = measure([cli, "verify", str(encoded), "--json"])
            summary = json.loads(measured.pop("stdout"))
            assert summary["integrity"] == "Md5Verified"
            assert summary["samples"] == duration * 48000
            measured["decoder_peak_compressed_bytes"] = summary["peak_compressed_buffer"]
            row["moonflac_runs"].append(measured)
            baseline = measure([flac, "--silent", "-t", str(encoded)])
            baseline.pop("stdout")
            row["libflac_runs"].append(baseline)
        median = statistics.median(x["seconds"] for x in row["moonflac_runs"])
        row["median_seconds"] = median
        row["audio_realtime_multiple"] = duration / median
        row["pcm_mib_per_second"] = row["raw_bytes"] / 1048576 / median
        row["max_os_peak_working_set_bytes"] = max(x["os_peak_working_set_bytes"] for x in row["moonflac_runs"])
        row["libflac_median_seconds"] = statistics.median(x["seconds"] for x in row["libflac_runs"])
        report["results"].append(row)
        (args.directory / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: row[k] for k in ("duration_seconds", "median_seconds", "audio_realtime_multiple", "max_os_peak_working_set_bytes")}), flush=True)
    print(f"Saved {args.directory / 'results.json'}")


if __name__ == "__main__":
    main()
