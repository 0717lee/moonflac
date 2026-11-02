# Native command line

Build from the project root with `moon build --target native`. Run using
`moon run cmd/moonflac --target native -- --help`, or invoke the resulting
`_build/native/debug/build/cmd/moonflac/moonflac.exe` in the verified Windows
toolchain. Check the actual output filename on other platforms.

```text
moonflac info input.flac --json
moonflac verify input.flac
moonflac decode input.flac output.wav
moonflac decode input.flac output.raw --raw --start 48000 --end 96000
moonflac decode input.flac output.wav --rf64
moonflac encode input.wav output.flac --effort 5
moonflac encode input.pcm output.flac --raw --sample-rate 48000 --channels 2 --bits 24
```

Both native FLAC and Ogg FLAC use the same commands. `info` and `verify`
decode and validate the complete input, including CRCs and any available
STREAMINFO MD5; `info` therefore also reports damaged audio as a failure.
Samples are counted per channel. Ranges are zero-based and end-exclusive;
even when exporting a range, the entire stream is validated.

Raw PCM is interleaved signed little-endian, unshifted and sign-extended to
`ceil(bits_per_sample / 8)` bytes. WAV PCM is left-aligned in that container;
8-bit containers are unsigned. WAV uses extensible headers when needed,
FLAC channel order, and a zero padding byte for odd data lengths. RF64 is
chosen for large data or unknown total sample counts, and can be forced.
Unknown total samples cannot be used to preallocate a RIFF header safely,
so even a short unknown-length stream produces RF64.
Ogg input also defaults to RF64 because later chained logical streams can
increase its total duration. Chains are exported consecutively; WAV requires
identical audio dimensions throughout, while raw PCM permits changes. JSON
reports the number of links, first-link metadata and whole-input sample/frame
counts. Aggregate MD5 is verified only when every link supplies a matching hash.

WAV/RF64 export preserves the case-insensitive
`WAVEFORMATEXTENSIBLE_CHANNEL_MASK` Vorbis comment. Absence selects the FLAC
default speaker order; explicit `0x0` remains unspecified. Partial masks are
preserved without imposing a speaker-count-equals-channel-count restriction.
Chained WAV export compares the effective layout as well as dimensions:
absent and explicit-default masks are compatible, differing layouts fail with
exit 3. Raw output and inspection still accept links with differing layouts.

Decoding retains a 64 KiB input chunk, the library's bounded compressed
buffer, metadata and the current PCM frame. It never collects whole-stream
PCM. The output must be a seekable file so its final WAV/RF64 header can be
rewritten. An existing output file is overwritten. On corruption or I/O
failure, a partial output can remain and must not be used. Input/output
identity is rejected, including ordinary hard links. PCM export rejects
changing stream dimensions because one WAV header cannot represent them.

Every command accepts `--max-buffer BYTES` to adjust the default 33,554,432-byte
decoder resource limit. Legal metadata can exceed that default; for example,
`moonflac verify large-metadata.flac --max-buffer 134217728` permits 128 MiB.
Accepted values are 4 through 2,147,483,647 bytes; actual allocation remains
subject to available memory. This is a retained-compressed-input limit, not a
total process-memory budget, and large parsed metadata also consumes memory.

Exit statuses: `0` success, `2` invalid arguments/range, `3` malformed,
truncated or unsupported-by-resource-limits input, `4` file I/O failure.
Diagnostics use stderr; successful summaries and JSON use stdout.

Executable interoperability checks (requires independently installed
libFLAC):

```text
python cmd/test_cli.py --cli PATH_TO_MOONFLAC --flac PATH_TO_FLAC
```

The script creates known integer PCM, encodes with libFLAC, checks 8/16/24/32
bit raw output and exact ranges, re-encodes exported WAV/RF64 with libFLAC,
compares decoded raw bytes, and checks truncation, argument and I/O exits.
All temporary audio artifacts are removed by Python's temporary directory.
Layout fixtures use Python-generated extensible WAV independently encoded and
decoded by libFLAC, including side 5.1 (`0x060f`), a partial four-channel mask,
mixed-case tags, a 16-bit stereo extensible header and Ogg chains. Pass
`--layout-fixtures validation/cache/review-layout` to retain these fixtures for
browser tests. libFLAC 1.5 decodes an explicit zero mask as its default; MoonFLAC
instead preserves explicit `0x0`, checked against the input metadata contract.

`io.c` implements file and stderr I/O only; all FLAC parsing, predictors,
checksums, MD5, Ogg demultiplexing and WAV serialization remain MoonBit.

## Encoding

`encode INPUT OUTPUT` accepts integer RIFF WAVE or RF64 and produces native
FLAC. It streams chunk headers, skips unknown chunks and reads PCM through
the pure MoonBit `PcmInput` API. PCM staging is at most 64 KiB; emitted batches
contain at most 4096 integer channel values in complete sample frames. The
encoder consumes these batches incrementally and the CLI rewrites its final
STREAMINFO header to contain the exact total, MD5 and observed frame sizes.
Input PCM and encoded bytes are never collected for the full file.

WAV supports 8/16/24/32-bit containers with 4–32 valid bits. Extensible PCM
valid bits are left-aligned; unused low bits must be zero. Eight-bit containers
are unsigned. Extensible channel masks, including explicit zero and partial
masks, are preserved. RIFF boundaries, chunk padding, data alignment, format
dimensions and RF64 `ds64` sizes/counts are checked. RF64 extra size tables have
an explicit 65,536-entry limit. IEEE float and other compressed WAVE subformats
are rejected with a diagnostic. Optional non-PCM WAV metadata is skipped; this
command does not translate arbitrary RIFF metadata into FLAC metadata blocks.

`--raw` requires `--sample-rate`, `--channels` and `--bits`. Its integer byte
format is the same signed, little-endian, unshifted, sign-extended format used
by `decode --raw`. Incomplete channel groups and samples outside the declared
bit depth fail. A zero sample rate requires explicit `--non-audio`.

Encoder options:

- `--block-size 16..65535` (default 4096).
- `--effort 0..8` (default 5).
- `--variable-block` selects variable blocking.
- `--channel-mask HEX` supplies or overrides layout; `0x` is optional.
- `--max-buffer BYTES` sets the encoder metadata budget; PCM staging retains
  its fixed 64 KiB bound.

Output must be a seekable file. The same input/output identity protection and
partial-file-on-error contract applies as for decoding. Encoding does not take
the decode-only crop or `--rf64` options; RF64 is an input container here.

```text
python cmd/test_encoder_cli.py --cli PATH_TO_MOONFLAC --flac PATH_TO_FLAC
python cmd/benchmark_encoder.py --cli PATH_TO_MOONFLAC --flac PATH_TO_FLAC
```

The encoder CLI tests independently construct WAV/RF64 PCM and decode the
result through the official libFLAC library, including all 29 valid bit depths.
Pass `--libflac PATH` when the library is not in the validation cache or system
loader path. The reference executable also checks standard raw interoperability.
The native long-stream benchmark records process memory and original-PCM MD5
checks separately from compression-quality measurements.
