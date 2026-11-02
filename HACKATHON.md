# MoonFLAC · 2026 MoonBit 黑客松项目说明

> 提交状态（2026-11-02）：公开仓库已上线，GitHub Actions 干净环境通过（[CI workflow](https://github.com/0717lee/moonflac/actions/workflows/ci.yml)）；报名表与赛事群需要参赛者本人完成。官网当前仍显示“十月赛，10 月 31 日截止”，下一赛期以官方页面/赛事群通知为准。本文按“已有项目实质新增”准备；若官方将首次公开申报视为新项目，则按新项目填写，不重复提交。

报名表可直接复制 [SUBMISSION.md](SUBMISSION.md) 中的短版/长版字段。

## 一句话

MoonFLAC 是纯 MoonBit 实现的 FLAC 无损编解码库：同一套代码运行在 native、JavaScript 和 WebAssembly GC，覆盖解码、编码、Ogg 封装、流式处理、精确裁剪、CLI 和浏览器播放器，核心不依赖 libFLAC、FFmpeg、FFI 或浏览器内建音频解码器。

- 仓库：<https://github.com/0717lee/moonflac>
- 作者：谦友Lee（GitHub `0717lee`）
- 许可证：Apache-2.0
- 方向：工具库 / 基础软件 / 音频编解码
- 规模：1 人（可按赛事规则组队至 3 人）

## 真实需求

FLAC 是无损音频的事实标准之一，但 MoonBit 生态缺少一套可直接用于播放器、音频工具和服务端处理的完整实现。现有方案通常依赖 C 库、FFmpeg 或浏览器内置解码器，难以同时满足跨后端、可测试、无 FFI 和可审计的要求。

MoonFLAC 把“解析位流、恢复预测、声道去相关、校验、元数据、容器和工具链”放在同一个 MoonBit 代码库中，让 MoonBit 项目可以直接读写 FLAC，而不必为每个目标平台引入不同的原生依赖。

## 为什么适合 MoonBit

- **位流与整数运算密集**：FLAC 的 Rice 编码、LPC 预测、CRC/MD5 和 33-bit side channel 需要精确的整数语义；MoonBit 的强类型和多后端适合把同一份实现编译到 native/JS/wasm-gc。
- **跨端复用**：浏览器 Playground、native CLI 和库 API 共享同一套解码/编码核心，不需要为 Web 再写一份 JavaScript 解码器。
- **可验证**：项目把 RFC 9639 条款、实现文件和测试证据做成矩阵，并用独立 libFLAC 逐样本对照，而不是只比较“能否播放”。
- **生态价值**：音频是通用基础能力；一个可复用的 FLAC 库可以服务播放器、音频编辑、语音数据管线和 Web 应用。

## 本期实质新增（2026-11）

此前项目已完成解码器、原生编码器、CLI、浏览器 Playground 和独立验证。本期新增的不是改名或简单修补，而是补齐此前明确列为边界外的 **Ogg FLAC 输出**：

- `ogg_from_flac(native)`：验证原生 FLAC 帧索引后，生成单逻辑流 Ogg FLAC；保留 STREAMINFO/元数据，必要时补空 Vorbis 注释包。
- `encode_ogg_pcm(samples, config)`：整段 PCM → 原生 FLAC → Ogg FLAC 的便捷 API。
- `moonflac ogg INPUT OUTPUT [--serial HEX]`：可运行的 native CLI 路径。
- Ogg 页 CRC、sequence、continuation、granule、EOS 和跨页大帧处理；输出可被自身 `OggDemux` 和独立 libFLAC 接受。
- 新增 3 个 Ogg 测试；三后端各 **196/196** 项目测试通过；16/24/32-bit、2/6/8 声道输出经 libFLAC 解码后逐字节等于源 PCM。
- 公开仓库、CI、可复现演示和一页说明，作为可持续维护的提交基线。

边界：`ogg` CLI 当前把原生输入整体读入内存；原生 `Encoder` 仍是有界流式路径。MP4/Matroska、Ogg 流式写入器、系统播放器后端不在本期范围。

## 评审 5 分钟路径

```sh
moon version
moon fmt --check
moon check --target native
moon test --target native
moon build --target native
moon run examples/stream --target native
moon run examples/encode --target native
moon run examples/ogg --target native
```

```sh
# 生成一个 Ogg FLAC，并用独立 libFLAC 检查
moon run cmd/moonflac --target native -- encode input.wav output.flac
moon run cmd/moonflac --target native -- ogg output.flac output.oga
moon run cmd/moonflac --target native -- info output.oga
flac -t output.oga
flac -d --force-raw-format --endian=little --sign=signed -o output.raw output.oga
```

浏览器：

```sh
node playground/build.mjs
node playground/serve.mjs
# 打开 http://127.0.0.1:8080，分别选择 JavaScript / WebAssembly GC
```

## 验收对照

| 赛事要求 | 本项目对应证据 |
|---|---|
| 以 MoonBit 为主要实现语言 | 根库、CLI、浏览器桥接和 Ogg 封装均为 MoonBit；核心无 FFI |
| 仓库公开、提交可追踪 | GitHub 公开仓库；本期新增以独立提交记录，保留 Issue/PR 入口 |
| 清晰 README、可运行示例、必要测试 | 英文/中文 README、`examples/stream`、`examples/encode`、`examples/ogg`、196 个项目测试、CLI 合同测试 |
| 已有项目包含本期实质新增 | Ogg FLAC 输出 API + CLI + 跨页帧处理 + 独立 libFLAC 验证 |
| 开源合规、说明参考来源 | Apache-2.0；`THIRD_PARTY.md`；RFC 9639；libFLAC 仅用于外部验证 |
| 可解释、可维护 | `docs/SPEC-MATRIX.md`、`docs/ACCEPTANCE.md`、`docs/API.md`、`docs/CONTEST.md` |

## 历史验证摘要

这些结果在 Ogg 增量之前已完成，作为项目基线保留；详细范围和限制见 `docs/ACCEPTANCE.md`，不把历史结果混入本期新增：

- 解码：245/245 生成用例、64/64 公共 subset、11/11 uncommon 逐帧、11/11 faulty 拒绝。
- 编码：328 个独立原生案例、828 条跨后端流、137 种写出表示、全部 75 个有效公共文件完整重编码，50,363,649 个样本帧逐样本一致。
- 长流/RF64：实际处理 5,529,600,104 字节输入/输出；三后端测试、浏览器真实交互和持续压力均有记录。
- 性能目标“超过 libFLAC”仍未完成，文档不把它写成已达成。

## 原创与 AI 使用说明

项目由作者设计、实现和维护；AI 工具用于代码生成、测试补充、文档整理和审查辅助。作者能够解释 FLAC 位流、预测/残差、Ogg 页、资源边界和验证方法，并对最终代码质量负责。项目不包含其他参赛作品的代码或夹具；libFLAC、FFmpeg 和公共 FLAC 测试语料仅作为外部对照，来源和许可证记录在 `THIRD_PARTY.md` 与 `validation/README.md`。

## 提交前待办

- [x] 公开仓库：<https://github.com/0717lee/moonflac>，Apache-2.0，README/测试/演示可从干净 clone 复现。
- [x] 干净环境 CI：三后端 check/test/build、libFLAC 对照、CLI 合同测试和浏览器构建通过。
- [x] 可追踪评审记录：公开 PR <https://github.com/0717lee/moonflac/pull/1>。
- [x] 提交事项跟踪：公开 Issue <https://github.com/0717lee/moonflac/issues/3>。
- [x] 干净 clone 复核：native/JS/wasm-gc 各 196/196，CLI 合同测试通过。
- [x] 一页项目说明：本文件；技术细节见 `docs/ACCEPTANCE.md`、`docs/SPEC-MATRIX.md` 和 `docs/API.md`。
- [x] 本期实质新增：Ogg FLAC 输出、CLI `ogg`、跨页帧处理与独立 libFLAC 验证。
- [ ] 在官方报名表填写项目信息、GitHub ID、仓库地址和一页说明（可直接使用本文件）。
- [ ] 加入赛事交流群，把群昵称改为 GitHub ID；奖金发放依赖于此。
- [ ] 确认当前开放赛期（官网/群公告）；若 10 月赛已关闭，按下一月度赛期或官方指定的季度社区项目入口提交。
- [ ] 如需演示视频，按报名表要求录制“Ogg 输出 + libFLAC 验证 + 浏览器双后端”三段，不虚构远端 CI 或未执行的平台结果。
