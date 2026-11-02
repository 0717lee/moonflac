# Measured native streaming performance

Measured locally on 2026-09-29. These are generated stereo tones, **not real
recordings**, and are one reproducible workload rather than a general claim
about every predictor, bit depth, channel count or machine.

## Environment and method

- Windows build 26200, AMD Ryzen 7 8845H, approximately 27.8 GiB physical RAM.
- Moon `0.1.20260827 (d0aaa07 2026-08-27)`;
  compiler `v0.10.11+6ff76a5f9 (2026-08-28)`.
- Native release build; Python 3.11.7, psutil 7.2.2.
- FFmpeg `9.0.1-full_build-www.gyan.dev`; reference libFLAC 1.5.0.
- Binary SHA-256 for this measurement snapshot:
  `0b70018b63a4c6fadb0eccf816ef0d83d6d89b26d194400b751fc2eb36117f11`.

FFmpeg generates 48,000 Hz, two-channel signed 24-bit PCM: amplitude 0.6,
440 Hz left and 997 Hz right. libFLAC `-8` independently encodes the raw PCM.
The script hashes the source PCM and checks it against the actual STREAMINFO
MD5 bytes. Every timed MoonFLAC run completes full frame decoding, CRC checks
and MD5 verification, reports `Md5Verified`, and produces the expected sample
count. No MoonFLAC-generated PCM is used as the correct reference.

The measured command is `moonflac verify INPUT --json`. It performs complete
integer PCM reconstruction and integrity validation, discarding each consumed
frame. It does not include writing WAV or PCM output. The baseline is the
separate reference executable `flac --silent -t INPUT`.

Each input has three separate process runs. Wall time includes process startup
and disk reads. Filesystem caches are warmed by input generation and repeated
reads; CPU affinity and power state are not controlled. There were other local
development processes, so individual-run variation is shown below. Memory is
polled every 5 ms with psutil. On Windows, `peak_wset` is the operating system's
process working-set high-water mark observed before exit, rather than only the
largest current-RSS polling sample.

## Results

| Audio duration | Input FLAC bytes | Decoded PCM bytes | Median wall seconds | Audio / wall time | PCM MiB/s | Max OS peak working set | Decoder compressed peak |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 s | 461,436 | 1,440,000 | 0.088585 | 56.44× | 15.50 | 9,068,544 B | 24,810 B |
| 60 s | 5,440,834 | 17,280,000 | 0.627185 | 95.67× | 26.28 | 9,093,120 B | 25,191 B |
| 300 s | 27,176,530 | 86,400,000 | 2.656305 | 112.94× | 31.02 | 9,400,320 B | 25,037 B |

The three MoonFLAC wall times were:

| Duration | Run 1 | Run 2 | Run 3 | Reference libFLAC median |
|---:|---:|---:|---:|---:|
| 5 s | 0.088585 s | 0.078470 s | 0.093426 s | 0.037553 s |
| 60 s | 0.627185 s | 0.643002 s | 0.619036 s | 0.100535 s |
| 300 s | 2.730825 s | 2.656305 s | 2.654490 s | 0.359472 s |

The shortest-run timing is particularly sensitive to startup and scheduling.
The 300-second runs provided 417, 445 and 439 successful memory samples. For a
60× increase in audio duration, maximum process working set increased by
331,776 bytes (324 KiB), while decoded PCM grew by 84,960,000
bytes. This is observed evidence that this streaming CLI path does not retain
the entire compressed file or decoded audio on this workload.

The decoder statistic counts retained native compressed input; it is not total
process memory. Process working set also includes runtime code, metadata,
the 64 KiB CLI read chunk, current frame and allocator overhead. This benchmark
does not establish bounds for arbitrary-sized metadata, deliberately malicious
inputs, the collecting `decode` API, browser PCM storage or every Ogg mapping
case. Those contracts and tests are separate from this native timing result.

## Reproduce

From the project root, with FFmpeg, libFLAC and Python psutil available:

```powershell
moon build --target native --release --target-dir _build/bench
python cmd/benchmark.py --cli _build/bench/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe
```

Use the actual executable paths for your platform. The script accepts
`--ffmpeg`, `--durations 5 60 300`, `--repeats 3`, and `--directory`.
Artifacts and all individual memory/time measurements are written beneath
`validation/cache/benchmark/`; `results.json` records versions, source
parameters, binary/input hashes and per-process measurements. This cache is
reproducible and excluded from distribution.

The exact generation filter is:

```text
aevalsrc=0.6*sin(2*PI*440*t)|0.6*sin(2*PI*997*t):s=48000
```

libFLAC options:

```text
-8 --force-raw-format --endian=little --sign=signed --channels=2 --bps=24 --sample-rate=48000
```

| Duration | Source PCM MD5 | Encoded FLAC SHA-256 |
|---:|---|---|
| 5 s | `2d297c04de3b6008abb172043cbc0a32` | `3c6f260addde8cdea1d544970764ac1f0d344acd02a350a54051d043277229fd` |
| 60 s | `fe3ee8377028e243ec5ab8cea1f194c0` | `448951fad40a00ebbc03b9fc80c9fdcdaf3177b4fd43e499a543c794bf4bf90e` |
| 300 s | `fa6e56613e5fc5b6759827df3aafabef` | `62f2c01f66425eeab0ae279dc8d7234dc1641a6fb154b463aa843a4fe535185b` |

Different FFmpeg/libFLAC versions may generate different low-order samples or
encoded bytes; the script always derives and checks the independent reference
for the versions actually used. Local measurements do not imply remote CI or
other-platform measurements have run.

## Encoder streaming memory experiment

The encoder was measured separately after its implementation and final constant
subframe cost fix, using a native release executable built at 13:52:53 on
2026-09-29. Binary SHA-256:
`493bdb4dbd023802a8795740550e499244618a0785f06140192267c12255e21a`.
The hardware, compiler and generated stereo 24-bit tone source are the same as
above. These are **single-process observations**, not repeated-run medians.
Other development benchmarks may have shared the CPU, and the first process
includes cold startup effects. Wall times characterize these observations;
the purpose here is to test bounded memory as stream length and block size vary.

Every command performs complete raw-PCM encoding and final header replacement.
The source PCM MD5 is independently computed in Python, compared with the exact
16 STREAMINFO bytes, and the 36-bit total sample count is checked against the
source length. Official libFLAC `flac --silent -t` then independently decodes
and verifies every generated file, including its MD5. Neither full PCM output
nor the reference process is retained inside the measured MoonFLAC process.

| Effort | Block size | Audio duration | Input PCM bytes | Output FLAC bytes | Wall seconds | Max OS peak working set | Memory polls |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4096 | 5 s | 1,440,000 | 1,440,750 | 0.312061 | 9,957,376 B | 17 |
| 0 | 4096 | 60 s | 17,280,000 | 17,289,066 | 0.731327 | 8,228,864 B | 108 |
| 0 | 4096 | 300 s | 86,400,000 | 86,447,090 | 2.895318 | 8,757,248 B | 436 |
| 5 | 4096 | 5 s | 1,440,000 | 463,190 | 0.889079 | 9,216,000 B | 132 |
| 5 | 4096 | 30 s | 8,640,000 | 2,789,087 | 5.259033 | 9,519,104 B | 811 |
| 5 | 65535 | 5 s | 1,440,000 | 458,868 | 0.509965 | 13,762,560 B | 75 |

The effort-0 cases primarily exercise low-cost candidate selection and sustained
I/O; their encoded size is slightly larger than PCM and is not a compression
quality claim. Their process high-water marks do not grow with the 60× increase
in input duration. Predictor-enabled effort 5 increases from 9,216,000 to
9,519,104 bytes for 6× the input duration (a 303,104-byte difference). Raising
the block size to 65,535 increases working memory to 13,762,560 bytes; that
five-second case emits four frames and exercises more than two full maximum
blocks. This is consistent with block-bounded predictor work rather than
whole-stream storage. Higher effort/compression-ratio comparisons are recorded
separately by the encoder acceptance tooling.

The CLI PCM reader retains at most 65,536 input bytes and emits batches of at
most 4096 scalar samples; the encoder has its own block-sized state. This
experiment does not claim a universal RSS ceiling for every bit depth, channel
count, effort, metadata payload or runtime allocator.

Reproduce from the project root:

```powershell
moon build --target native --release --target-dir _build/encoder-cli-release
python cmd/benchmark_encoder.py --cli _build/encoder-cli-release/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe
python cmd/benchmark_encoder.py --cli _build/encoder-cli-release/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --effort 5 --durations 5 30 --directory validation/cache/encoder-memory/effort5
python cmd/benchmark_encoder.py --cli _build/encoder-cli-release/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --effort 5 --durations 5 --block-size 65535 --directory validation/cache/encoder-memory/maxblock
```

The script reuses matching-size generated tone raw inputs or creates missing
inputs with the disclosed FFmpeg filter. It always hashes the actual raw input
used. Per-process reports are `results.json` in the specified directories;
the 30-second source PCM MD5 is `44fa29fda0ba606df27cc42a288c3548`, with other
source hashes listed above. Cache artifacts remain reproducible local evidence.

## Performance-hardening reproduction

The newer paired experiment and long-stream results are summarized in
[PERFORMANCE.md](PERFORMANCE.md), with the complete local evidence index in
`validation/evidence/hardening-final.json`. The production CLI used throughout
has SHA256 `179b27506f7bc226750fe7efdddd4653d4df8c9f689b98a7787252c3a84e69fe`.
The earlier single-run measurements above remain historical snapshots.

From the project root on Windows, with the pinned MoonBit compiler, Node,
Python/psutil, FFmpeg and the prepared libFLAC 1.5 reference:

```powershell
python scripts/profile_encoder.py freeze --historical
moon build --target native --release --target-dir _build/hardening/candidate
python scripts/benchmark_hardening.py --baseline _build/hardening/baseline/_build/native/release/build/cmd/moonflac/moonflac.exe --candidate _build/hardening/candidate/native/release/build/cmd/moonflac/moonflac.exe
python scripts/validate_hardening.py
python scripts/stress_encoder.py long --cli _build/hardening/candidate/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --report validation/evidence/hardening-long.json
python scripts/stress_encoder.py fuzz --cli _build/hardening/candidate/native/release/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --seconds 1800 --directory validation/cache/hardening-fuzz-journal --report validation/evidence/hardening-fuzz-journal.json
python scripts/classify_stress.py --journal validation/evidence/hardening-fuzz-journal.json --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --report validation/evidence/hardening-fuzz-classification.json
python scripts/validate_large_decode.py --long-report validation/evidence/hardening-long.json --report validation/evidence/hardening-large-decode.json
```

Preserve existing evidence or choose separate report paths for a new experiment.
Do not overlap controlled benchmark timing with builds or stress. The historical
freeze refuses to overwrite an existing snapshot. For isolated core timing,
use `benchmark_hardening.py --core` with the two corresponding
`validation/benchmark/benchmark.exe` paths and a separate `--report`.

Actual Linux execution used Ubuntu 22.04.5 WSL2, GCC 11.4.0, the same MoonBit
compiler, Node 22.23.3 and a task-local libFLAC 1.5.0 build. To reproduce the
reference dependencies under the paths expected by `validate_linux_hardening.py`,
start from the project root with a matching Moon installation on PATH and
`MOON_HOME` explicitly set to that installation (the pinned installation command
is also in `.github/workflows/ci.yml`):

```sh
tools_dir="$PWD/_build/hardening/linux-tools"
mkdir -p "$tools_dir"
cd "$tools_dir"
curl -fLO https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz
printf '%s\n' 'df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de  node-v22.23.3-linux-x64.tar.xz' | sha256sum -c -
tar -xf node-v22.23.3-linux-x64.tar.xz
curl -fLO https://ftp.osuosl.org/pub/xiph/releases/flac/flac-1.5.0.tar.xz
printf '%s\n' 'f2c1c76592a82ffff8413ba3c4a1299b6c7ab06c734dee03fd88630485c2b920  flac-1.5.0.tar.xz' | sha256sum -c -
tar -xf flac-1.5.0.tar.xz
cd flac-1.5.0
./configure --prefix="$tools_dir/flac-prefix" --disable-ogg --disable-cpplibs --disable-doxygen-docs --disable-thorough-tests
make -j2
make install
cd ../../../..
moon update
python3 scripts/validate_linux_hardening.py
```

This reference build has Ogg disabled; it verifies the native encoder here.
Linux FFmpeg and independent Linux hardware/macOS were not part of this run.
The runner uses a separate build directory and explicit Linux libFLAC paths,
so it cannot accidentally load the cached Windows DLL. The original WSL `/tmp`
build was cleared when that environment stopped; the permanent runner, source
hashes, output hashes and command logs retain reproducibility without depending
on that temporary path. None of these local results claim remote CI execution.
