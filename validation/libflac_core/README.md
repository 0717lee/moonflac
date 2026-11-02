# libFLAC owned-buffer reference harness

This is an external validation/benchmark program. MoonFLAC does not link it or
call libFLAC for its codec implementation. It uses the official Xiph FLAC 1.5.0
Win64 `libFLAC.dll`, matching release headers, and a small MSVC `/O2 /MT` harness.
No scalar-only replacement, assembly-disable option, verification decoder,
thread pool, or encoder reuse is introduced.
Each call explicitly requests one libFLAC thread and checks that the returned
thread-limit setting is one; it does not rely solely on the library default.

From the project root on Windows:

```powershell
python scripts/build_libflac_core.py --report validation/evidence/faster-than-libflac-core-harness-final.json
_build/faster-than-libflac/core-reference/libflac_core.exe input.raw output.flac 2 24 48000 4096 5 8
```

Arguments are `input output channels bits sample-rate block-size batch effort`.
Effort accepts 0–8; formats accept 1–8 channels, 4–32 valid bits, rates 0–1048575,
and explicit block sizes 16–65535. Inputs contain signed, little-endian integers
in `ceil(bits / 8)` bytes; non-byte widths must be sign-extended. Whole nonempty
interleaved frames are required. This in-memory benchmark is limited by available
memory, the `unsigned` frame count and C `long` file offsets (below 2 GiB on this
Windows build); it is not the long-stream stress runner.

The build script refuses to overwrite an evidence report. Its defaults reuse
the project-cached official DLL and headers installed from the checksum-verified
FLAC 1.5.0 release archive during Linux-tool preparation. `--headers`,
`--reference-dir`, `--build-dir`, and `--report` permit explicit alternatives.
No global compiler or environment settings are changed. Generated import
libraries, the copied DLL, compiler output, logs and smoke fixtures remain under
the selected build directory. Source and headers are hashed in the report.

## Timing contract

Each invocation first reads and unpacks the raw input into an immutable
`FLAC__int32[]`. It performs one warm encode, then exactly `batch` measured calls.
Each call includes:

- allocating a fresh encoder and applying all settings;
- initializing a native FLAC stream with memory write/seek/tell callbacks;
- processing the already-prepared interleaved PCM;
- finishing the stream, including its PCM MD5 and final STREAMINFO rewrite;
- destroying the encoder and all its internal state;
- allocating/growing its own complete output buffer, including frame CRCs.

The output has independent ownership and a length; capacity may exceed length.
The memory writer doubles capacity as needed and does not borrow prior output or
retain any encoder between calls. A fixed-block stream and no optional metadata,
padding or seek table are requested. The streamable-subset restriction is off so
the full stated input domain is usable; normal library compression-level search
and SIMD dispatch remain enabled. libFLAC's encode-then-decode verification mode
is disabled because verification is performed independently outside timing.

The timer stops before output equality comparison and freeing the returned
output. This matches the inspected native C for `validation/benchmark8/main.mbt`:
`encode_pcm` returns, `monotonic_clock_end` executes, then `assert_eq` and
`moonbit_decref(encoded)` execute. The warm owned output remains alive throughout
the batch in both harnesses. Input unpacking, file reads/writes, comparisons,
printing and independent validation are excluded. Encoder destruction is inside
the timer, while final output-buffer destruction is outside it. No per-call
output allocation is reused to hide this cost.

Output is one `LIBFLAC_CORE ` line followed by JSON with `warm_seconds`, every
`per_call_seconds`, their sum `seconds`, batch/effort/frame counts, and the final
output size/capacity. Windows uses QueryPerformanceCounter. A POSIX monotonic
clock implementation is present, but this builder and its acceptance evidence
cover Windows only. The Linux build would need an explicit native-library build
and its own evidence before being claimed as validated.

## Evidence and comparison limits

The builder records the compiler path/hash, harness flags/source/executable
hashes, DLL hash, FLAC version, header hashes and CPU/OS SIMD capabilities. DLL
disassembly records XMM/YMM/ZMM register occurrence counts, demonstrating SIMD
code presence; these counts do **not** identify the runtime-selected function.
The official release archive does not record its exact compiler invocation, so
the DLL's original compiler flags are explicitly recorded as unknown. The
harness `/O2` flags must not be presented as the DLL's build flags.

Smoke checks cover 16/24/32-bit, 1/2/6/8 channels, efforts 0/5/8, signed extrema
and seeded noise, with one warm call and two measured calls. Every output is
decoded independently by the official command-line tool, compared byte-for-byte
with the original raw PCM, checked with `flac -t`, and its stored MD5 is compared
with Python's hash of the original PCM. Smoke timings only validate plumbing;
they are not controlled performance results and must not enter a speedup table.

Before a controlled Moon/libFLAC comparison, the Moon harness should accept an
effort argument and emit every call's duration (its current version fixes effort
8 and reports only a batch sum). Prepare duration storage outside the timed call
and keep the existing post-timer ownership/equality behavior. Inspect the final
candidate's generated C as well: the ownership observation above was made on the
existing native baseline build, and compilation changes could move lifetimes.
Use the same input, block size, batch count, warmup count, ordering, machine and
idle-load controls; report per-case compressed sizes as well as speed. This C
harness does not make compression-level numbers algorithmically equivalent.
