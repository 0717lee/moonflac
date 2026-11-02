# 报名表填写稿

> 字段以官方报名表为准；联系方式需本人补充。

## 基本信息

| 字段 | 内容 |
|---|---|
| 项目名称 | MoonFLAC |
| GitHub ID | `0717lee` |
| 仓库 | <https://github.com/0717lee/moonflac> |
| 许可证 | Apache-2.0 |
| 参赛形式 | 个人（1 人） |
| 方向 | 音频编解码基础库 / 工具库 |
| 赛道 | 已有项目实质新增；若官方按首次公开申报视为新项目，则按新项目填写，不重复提交 |

## 短版（约 150 字）

MoonFLAC 是纯 MoonBit 的 FLAC 无损编解码库，同一套代码运行在 native、JavaScript 和 WebAssembly GC，支持解码、编码、Ogg 输出、流式处理、精确裁剪、CLI 和浏览器 Playground，核心不依赖 libFLAC、FFmpeg 或 FFI。本期新增 Ogg FLAC 输出和 `moonflac ogg`，并完成 libFLAC 逐字节 PCM 验证。

## 长版（约 350 字）

MoonFLAC 为 MoonBit 生态补齐 FLAC 无损音频能力。项目实现 RFC 9639 的位流解析、预测恢复、声道去相关、CRC/MD5、元数据、Ogg 解复用、原生 FLAC 编码和 Ogg 封装；同一套核心编译到 native、JavaScript 和 wasm-gc，配套 CLI、浏览器 Playground、流式 API、精确样本裁剪和独立验证工具。核心不调用 libFLAC、FFmpeg、FFI 或浏览器音频解码器，libFLAC 仅用于外部对照。

本期新增 Ogg FLAC 输出：`ogg_from_flac` 验证原生帧索引后生成单逻辑流 Ogg，保留 STREAMINFO 和元数据；`encode_ogg_pcm` 提供整段 PCM 到 Ogg 的便捷路径；CLI 新增 `moonflac ogg`。实现覆盖 Ogg 页 CRC、sequence、continuation、granule、EOS 和跨页大帧。三后端各 197/197 测试通过；16/24/32-bit、2/6/8 声道输出经 libFLAC 解码后 PCM 逐字节一致。

## 演示

```sh
moon test --target native
moon run examples/ogg --target native
moon run cmd/moonflac --target native -- ogg output.flac output.oga
flac -t output.oga
```

浏览器：`node playground/build.mjs && node playground/serve.mjs`。

## 链接

- 一页说明：`HACKATHON.md`
- 验收摘要：`docs/ACCEPTANCE.md`
- Ogg 收据：`validation/evidence/2026-11-02-ogg-mux/README.md`
- CI：<https://github.com/0717lee/moonflac/actions/workflows/ci.yml>
- PR：<https://github.com/0717lee/moonflac/pull/1>、<https://github.com/0717lee/moonflac/pull/2>
- Issue：<https://github.com/0717lee/moonflac/issues/3>
