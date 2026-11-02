# MoonFLAC competition walkthrough / 比赛验收

MoonFLAC is the November project: a new pure MoonBit FLAC codec library and its tools. The core is independent of the neighboring PixelForge, MoonHostABI and MoonAV1 projects. This checkout is the public submission for the 2026 MoonBit Hackathon; the repository, CI run and remaining registration steps are recorded in [HACKATHON.md](../HACKATHON.md).

## Demonstration sequence

1. Run the three-target commands in the README. Show `examples/stream`: independent RFC Appendix D.1 bytes are fed one byte at a time and produce left=25588, right=10416 with `Md5Verified`.
2. Run `info` on an ordinary music FLAC to inspect STREAMINFO and structured metadata; run `verify` to establish CRC and supplied MD5 integrity. Repeat with 32-bit/multichannel data and Ogg input.
3. Export raw PCM and compare every byte with independently decoded libFLAC PCM through `scripts/validate.py`. The generated manifest records sample rate, depth, channels, sample count, source hash and expected PCM path. Do not substitute test counts for this comparison.
4. Export `[48000,96000)` or another in-range interval to WAV. Check the exact length with a separate WAV reader and compare corresponding source PCM. Inspect valid-bit depth, channel mask and RF64 headers where applicable.
5. Start the Playground, select and drag/drop input, inspect metadata and waveform, play/pause/seek and export WAV. Select both JavaScript and WebAssembly GC; each actual MoonBit artifact runs in its Worker and Web Audio receives PCM. Show measured decode/bridge and load/compile times separately, then compare exported WAV bytes across backends and open the result with an independent tool.
6. Demonstrate a damaged CRC and truncated file: both must report failure. Show long-stream compressed-buffer measurements separately from output/caller memory. Consult each public corpus group README before deciding a case should succeed or fail.

## Native encoder demonstration

The authorized encoder extension writes native FLAC on native, JS and wasm-gc; its completed gates and evidence are maintained in [the encoder ledger](ENCODER-PROPOSAL.md). Use the following steps to reproduce the accepted behavior:

1. Encode an integer WAV/RF64 with `moonflac encode source.wav output.flac`, independently decode the result with libFLAC, and compare integer PCM to the original source. Repeat with explicit raw 4–32-bit, 1–8-channel formats and nondefault masks.
2. Show `--effort 0`, `--effort 5` and `--effort 8`, then `--variable-block`. Inspect the emitted representation and report measured compression/time separately from lossless correctness. LPC analysis uses floating point to select candidates; reconstruction remains integer-exact.
3. Drive `Encoder` with arbitrary scalar-prefix splits, including splits inside channel groups; compare output across chunkings. Show bounded `peak_buffered_samples` and empty/partial/out-of-range failure cases.
4. Demonstrate both header paths: finalized `encode_pcm`/seekable CLI output with supplied MD5, and a non-seekable stream retaining unknown STREAMINFO fields while `EncoderSummary` still exposes the computed PCM digest.
5. Verify preserved metadata and channel masks, and show a supplied stale seek table being rejected against the newly emitted frames. Keep encoder references independent of MoonFLAC's decoder.
6. Run `moonflac ogg source.flac source.oga`, inspect it with `moonflac info`, and verify/decode it with independent libFLAC. Compare decoded PCM byte-for-byte. This exercises the 51-byte Ogg FLAC mapping packet, metadata packets, page CRC/sequence, frame continuation and EOS; the CLI stages the input in memory, while the native encoder remains the bounded streaming path.

## Evidence and acceptance

The source-level [acceptance matrix](ACCEPTANCE.md) and [specification mapping](SPEC-MATRIX.md) connect requirements to code and tests. [Preserved validation evidence](../validation/evidence/README.md) records the decoder baseline executed on 2026-09-29 before the encoder extension: 245/245 generated and 64/64 subset exact PCM comparisons, 11/11 uncommon per-frame comparisons, and 11/11 faulty-input rejections. This includes subset 55's 87.3 MB file with 82.2 MB of metadata under an explicit 128 MiB budget. All three backends passed check/build and 67/67 project tests, including 14/14 independent golden tests on each target. Source revision, executable hashes and exact reproduction commands are preserved alongside the reports.

Real Chromium interactions passed on JavaScript and wasm-gc, with actual backend artifact requests observed, no browser compressed-audio decoding, and byte-identical WAV exports on backend switching. Local measurements for real mono audio were 117.70 ms JS and 31.80 ms wasm-gc; high-rate LPC32 measurements were 4,307.60 ms and 796.90 ms. These single runs include host PCM transfer and exclude separately measured backend loading. See [performance](PERFORMANCE.md) and [browser reproduction](../playground/README.md) for scope and evidence paths.

CI is configured to build, check and test native/JS/wasm-gc, run the compiled streaming example, generate libFLAC reference data, compare native CLI PCM and run CLI interoperability checks. Browser real-interaction and the complete larger corpus were executed locally; merely building the browser bundle does not prove them. The workflow has not been run remotely, so no remote CI status is claimed.

## Evaluation boundaries

The product covers FLAC decoding, native/Ogg input integration, native FLAC encoding and Ogg FLAC muxing from completed native frames. A bounded Ogg streaming writer, unrelated codecs, browser audio editing/AudioWorklet playback and operating-system player backends remain outside this extension; the CLI `ogg` command stages its native input in memory. MP4/Matroska need their own container demultiplexers; their FLAC frames can be integrated through the raw-frame API. This is a container boundary, not a missing FLAC subframe mode.

Historical implicit variable-block streams are compatibility input described by RFC Appendix B.1; the implementation recognizes their constrained STREAMINFO/header pattern. Unknown metadata is retained rather than guessed. Full-file verification, raw-frame recovery and partial seeking have distinct integrity contracts. The browser demo retains PCM and has preview limits; the incremental library is the interface for long recordings.

## 中文验收要点

评审时同时展示规范矩阵、实际 PCM 对照、三个后端运行、损坏输入诊断、长流内存证据、CLI 互通与浏览器真实交互。逐样本一致证明无损正确性；编译通过和测试数量不能替代它。采样区间按每声道 `[start,end)` 计算；全局 MD5 只有完整流/链接结束后才能确认。浏览器播放的 Float32、设备重采样与整数 WAV 导出应明确区分。

新增编码器已完成原始 PCM → MoonBit 编码 → libFLAC 独立解码验收：328 个格式/信号/片段案例、三个后端共 828 条流，以及全部 75 个有效公共文件的完整 PCM（84 条同格式输出流，50,363,649 个样本帧）均逐样本一致；327 个音频案例还经过 FFmpeg 对照。137 种写出表示由官方工具独立解码与分析。当前 Windows 与 WSL2 三个后端各 99/99 测试通过；effort 压缩率/性能、任意分块、有界暂存、最大块和头部最终化的证据均见编码器台账。性能加固还实际处理并导出了超过 4 GiB 的 RF64 PCM，完成小时级高 effort 多声道长流和 30 分钟差分压力；最终独立审核状态见 ACCEPTANCE.md。前述历史基线与本轮证据分别保留。

公开仓库、CI 和 PR 记录已建立，作为 2026 MoonBit 黑客松的提交基线；生产部署仍不属于本次验收执行。
