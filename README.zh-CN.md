# MoonFLAC

[English](README.md) · [API](docs/API.md) · [验收摘要](docs/ACCEPTANCE.md) · [规范矩阵](docs/SPEC-MATRIX.md) · [黑客松说明](HACKATHON.md) · [CI](https://github.com/0717lee/moonflac/actions/workflows/ci.yml)

MoonFLAC 是面向 native、JavaScript 和 WebAssembly GC 的纯 MoonBit FLAC 无损编解码库，覆盖解码、原生 FLAC 编码、Ogg FLAC 封装、流式处理、精确裁剪、CLI 和浏览器 Playground。核心库不调用 libFLAC、FFmpeg、FFI 或浏览器音频解码器；libFLAC 仅用于外部验证。

## 功能

| 范围 | 支持 |
|---|---|
| PCM | 4–32 valid bits、1–8 声道、1–1,048,575 Hz |
| 帧 | 固定/可变块、16–65,535 样本、CRC8/CRC16 |
| 子帧 | constant、verbatim、fixed 0–4、LPC 1–32、Rice/Rice2、escape、wasted bits |
| 运算 | Int64 预测与立体声重建，覆盖 33-bit side channel |
| 元数据 | STREAMINFO、PADDING、APPLICATION、SEEKTABLE、VORBIS_COMMENT、CUESHEET、PICTURE；未知 7–126 保留 |
| 完整性 | 输出前检查帧 CRC；流/链接结束时校验可用 MD5 |
| 容器 | 原生/Ogg FLAC 解码（含串接）；原生帧封装为 Ogg FLAC |
| 访问 | 整文件/增量解码、帧索引、半开样本区间裁剪 |
| 输出 | Raw PCM、WAV、WAVE_FORMAT_EXTENSIBLE、RF64 |
| 编码 | 4–32-bit PCM 原生 FLAC；整段与有界流式 API；effort 0–8；Ogg 输出 |

实现依据 [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html)，并应用已核验勘误 [8256](https://www.rfc-editor.org/errata/eid8256)、[8810](https://www.rfc-editor.org/errata/eid8810)。

## 构建与测试

安装 [MoonBit 工具链](https://www.moonbitlang.com/download/)、本机 C 工具链、Node.js 和 Python 3。CI 固定编译器 `0.10.16+b1a0e846e`。

```sh
moon update
moon fmt --check
for target in native js wasm-gc; do
  moon check --target "$target"
  moon test --target "$target"
  moon build --target "$target"
  moon run examples/stream --target "$target"
  moon run examples/encode --target "$target"
  moon run examples/ogg --target "$target"
done
```

根库无平台 FFI；CLI 为 native，浏览器桥接面向 JavaScript 与 wasm-gc。

## CLI

```sh
moon run cmd/moonflac --target native -- info recording.flac --json
moon run cmd/moonflac --target native -- verify recording.flac
moon run cmd/moonflac --target native -- decode recording.flac output.wav
moon run cmd/moonflac --target native -- decode recording.flac excerpt.wav --start 48000 --end 96000
moon run cmd/moonflac --target native -- encode recording.wav output.flac
moon run cmd/moonflac --target native -- encode input.pcm output.flac --raw --sample-rate 48000 --channels 6 --bits 24 --channel-mask 0x060f
moon run cmd/moonflac --target native -- ogg output.flac output.oga
```

采样区间为从零开始、右端不包含的 `[start,end)`，按每声道计算。退出码：`0` 成功、`2` 参数错误、`3` 输入/资源限制、`4` 文件 I/O。所有命令支持 `--max-buffer BYTES`（默认 32 MiB）。

`encode` 读取整数 WAV/RF64；raw 输入必须提供采样率、声道数和位深。`--block-size` 默认 4096，`--effort` 默认 5，`--variable-block` 启用自适应分块。

## Ogg FLAC 输出

`ogg_from_flac(native)` 验证一份完整的原生 FLAC，并写出单逻辑流 Ogg FLAC，保留 STREAMINFO 和元数据。`encode_ogg_pcm(samples, config)` 是整段 PCM 到 Ogg 的便捷路径。

```sh
moonflac ogg recording.flac recording.oga
moonflac info recording.oga
```

`--serial HEX` 设置逻辑流序号；`--vendor NAME` 只在源文件没有 Vorbis 注释时设置 vendor。CLI 当前把输入整体读入内存；原生 `Encoder` 仍是有界流式路径。[`examples/ogg`](examples/ogg/main.mbt) 是三目标往返示例。

## 库与流式 API

以 `@flac` 导入 `0717lee/moonflac`。`decode(bytes)` 解码单个流，`decode_chained(bytes)` 分别返回 Ogg 链接。长流使用 `Decoder::new()`、`push`、`next`、`finish`，逐帧消费。所有权、错误、完整性时序和资源限制见 [API 文档](docs/API.md)。

`encode_pcm(samples, EncoderConfig::new(format))` 返回已最终化的原生 FLAC。`Encoder` 提供有界流式编码，保留 PCM 不超过 `block_size * channels`。`OggDemux` 提供增量 Ogg 输入。

## 浏览器 Playground

```sh
node playground/build.mjs
node playground/serve.mjs
```

打开 `http://127.0.0.1:8080`，选择 JavaScript 或 WebAssembly GC，查看元数据/波形，播放、暂停、定位并导出 WAV。MoonBit 产物在 Worker 中运行；整数 WAV 导出保留源精度。详见 [Playground 说明](playground/README.md)。

## 验证

- native、JavaScript、wasm-gc：各 **197/197** 项目测试。
- CI：三后端 check/test/build、CLI 合同测试、libFLAC PCM 对照和浏览器构建。
- 干净 clone：三后端 197/197，CLI 合同测试通过。
- Ogg 输出：libFLAC `-t` 通过；16/24/32-bit、2/6/8 声道 PCM 逐字节一致。
- 历史解码/编码/长流证据摘要见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

libFLAC 是独立 oracle；MoonFLAC 不使用自身解码结果作为参考。超过 libFLAC 的性能目标未完成。

## 边界

`ogg` CLI 会把输入整体读入内存。有界 Ogg 流式写入器、MP4/Matroska 映射、系统播放器后端和 AudioWorklet 播放不在范围内。资源限制会显式报错，异常大的合法输入可以提高限制。

Apache-2.0，见 [LICENSE](LICENSE) 和 [THIRD_PARTY.md](THIRD_PARTY.md)。当前检出即公开提交版本，见 [HACKATHON.md](HACKATHON.md)。
