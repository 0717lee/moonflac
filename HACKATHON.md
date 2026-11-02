# MoonFLAC · 2026 MoonBit 黑客松

> 状态（2026-11-02）：公开仓库、CI、Release、PR/Issue 已就绪；报名表和赛事群需本人完成。官网仍显示十月赛已截止，下一赛期以官方通知为准。

## 项目

MoonFLAC 是纯 MoonBit 的 FLAC 无损编解码库，支持 native、JavaScript 和 WebAssembly GC，覆盖解码、编码、Ogg FLAC 输出、流式处理、精确裁剪、CLI 和浏览器 Playground。核心不依赖 libFLAC、FFmpeg、FFI 或浏览器音频解码器。

- 仓库：<https://github.com/0717lee/moonflac>
- Mooncakes：<https://mooncakes.io/docs/0717lee/moonflac>
- 作者：谦友Lee（`0717lee`）
- 许可证：Apache-2.0
- 方向：音频编解码基础库 / 工具库
- 本期新增：Ogg FLAC 输出、CLI `ogg`、跨页帧处理

## 本期新增

`ogg_from_flac(native)` 验证原生 FLAC 帧索引后生成单逻辑流 Ogg，保留 STREAMINFO 和元数据；`encode_ogg_pcm` 提供整段 PCM 到 Ogg 的便捷路径；CLI 新增：

```sh
moonflac ogg input.flac output.oga [--serial HEX] [--vendor NAME]
```

实现覆盖 Ogg 页 CRC、sequence、continuation、granule、EOS 和跨页大帧。CLI 当前把输入整体读入内存；原生 `Encoder` 仍是有界流式路径。

## 验证

- native / JavaScript / wasm-gc：各 **197/197** 项目测试。
- CI：三后端 check/test/build、CLI 合同测试、libFLAC PCM 对照、浏览器构建。
- Ogg 输出经 libFLAC 1.5.0 `-t`；16/24/32-bit、2/6/8 声道 PCM 逐字节一致。
- 干净 clone 复核通过。

证据：[验收摘要](docs/ACCEPTANCE.md) · [Ogg 收据](validation/evidence/2026-11-02-ogg-mux/README.md) · [CI](https://github.com/0717lee/moonflac/actions/workflows/ci.yml)

## 评审路径

```sh
moon test --target native
moon run examples/stream --target native
moon run examples/encode --target native
moon run examples/ogg --target native
```

```sh
moon run cmd/moonflac --target native -- encode input.wav output.flac
moon run cmd/moonflac --target native -- ogg output.flac output.oga
moon run cmd/moonflac --target native -- info output.oga
flac -t output.oga
```

浏览器：`node playground/build.mjs && node playground/serve.mjs`，打开 `http://127.0.0.1:8080`。

## 边界

- 性能目标“超过 libFLAC”未完成。
- 有界 Ogg 流式写入器、MP4/Matroska、系统播放器、AudioWorklet 不在范围内。
- Mooncakes 已发布 `0.2.1`，GitHub Release 同步提供源码归档。

## 提交清单

- [x] 公开仓库、CI、Release、PR/Issue
- [x] 一页说明与报名表填写稿
- [x] 三后端测试和独立 libFLAC 验证
- [ ] 报名表、赛事群、当前赛期确认
- [ ] 如需，录制演示视频

报名表填写稿见 [SUBMISSION.md](SUBMISSION.md)。
