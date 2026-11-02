# 报名表填写稿 / Form-ready summary

> 报名表字段以官方实际页面为准。以下文本可直接复制；如果表单限制字数，优先使用“短版”。

## 基本信息

| 字段 | 内容 |
|---|---|
| 项目名称 | MoonFLAC |
| GitHub ID | `0717lee` |
| 仓库 | <https://github.com/0717lee/moonflac> |
| 许可证 | Apache-2.0 |
| 参赛形式 | 个人（1 人；如组队，队长 `0717lee`） |
| 方向 | 工具库 / 基础软件 / 音频编解码 |
| 赛道 | 已有项目实质新增（若官方将首次公开申报视为新项目，则按新项目填写，不重复提交） |
| 本期新增 | Ogg FLAC 输出、CLI `ogg`、跨页帧处理、独立 libFLAC 验证 |

## 一句话（约 50 字）

纯 MoonBit 实现的 FLAC 无损编解码库，覆盖 native/JS/wasm-gc、CLI 与浏览器，本期新增 Ogg FLAC 输出。

## 短版（约 150 字）

MoonFLAC 是纯 MoonBit 的 FLAC 无损编解码库，同一套代码运行在 native、JavaScript 和 WebAssembly GC，支持解码、编码、流式处理、精确裁剪、CLI 和浏览器播放器，核心不依赖 libFLAC、FFmpeg 或 FFI。本期新增 Ogg FLAC 输出：`ogg_from_flac`、`encode_ogg_pcm` 和 `moonflac ogg`，并完成跨页帧、CRC/granule/EOS 处理与 libFLAC 逐字节 PCM 验证。

## 长版（约 350 字）

MoonFLAC 解决 MoonBit 生态缺少完整 FLAC 实现的问题。项目用 MoonBit 实现 RFC 9639 的位流解析、预测恢复、声道去相关、CRC/MD5、元数据、Ogg 解复用，以及原生 FLAC 编码；同一套核心编译到 native、JavaScript 和 wasm-gc，配套 CLI、浏览器 Playground、流式 API、精确样本裁剪和独立参考验证工具。核心不调用 libFLAC、FFmpeg、FFI 或浏览器内建音频解码器，libFLAC 仅用于外部对照。

本期在既有解码/编码基础上新增 Ogg FLAC 输出：`ogg_from_flac` 在验证原生帧索引后生成单逻辑流 Ogg，保留 STREAMINFO/元数据；`encode_ogg_pcm` 提供整段 PCM 到 Ogg 的便捷路径；CLI 新增 `moonflac ogg`。实现覆盖 Ogg 页 CRC、sequence、continuation、granule、EOS 和跨页大帧。三后端各 196/196 项目测试通过，16/24/32-bit、2/6/8 声道输出经 libFLAC 解码后逐字节等于源 PCM。

## 演示入口

```sh
moon test --target native
moon run examples/stream --target native
moon run examples/encode --target native

moon run cmd/moonflac --target native -- encode input.wav output.flac
moon run cmd/moonflac --target native -- ogg output.flac output.oga
moon run cmd/moonflac --target native -- info output.oga
flac -t output.oga
```

浏览器：`node playground/build.mjs && node playground/serve.mjs`，打开 `http://127.0.0.1:8080`，分别切换 JavaScript / WebAssembly GC。

## 证据链接

- 一页说明：`HACKATHON.md`
- 验收台账：`docs/ACCEPTANCE.md`
- 规范矩阵：`docs/SPEC-MATRIX.md`
- API：`docs/API.md`
- 本期 Ogg 收据：`validation/evidence/2026-11-02-ogg-mux/README.md`
- CI：<https://github.com/0717lee/moonflac/actions/workflows/ci.yml>
- PR 记录：<https://github.com/0717lee/moonflac/pull/1>

## 仍需本人完成

- 在官方报名表提交上述信息；
- 加入赛事交流群并把昵称改为 `0717lee`；
- 确认当前开放赛期与赛道（官网目前显示十月赛已截止）。
