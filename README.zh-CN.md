# MoonFLAC

[English](README.md) · [API 契约](docs/API.md) · [功能验收矩阵](docs/ACCEPTANCE.md) · [比赛演示](docs/CONTEST.md) · [2026 黑客松说明](HACKATHON.md)

> **2026 MoonBit 黑客松：** 一页项目说明与本期提交边界见 [HACKATHON.md](HACKATHON.md)。公开仓库是提交记录；编解码库本身保持可复用。

MoonFLAC 是面向 native、JavaScript、wasm-gc 的纯 MoonBit FLAC 无损编解码库，配套 CLI、浏览器 Playground、示例和独立参考验证工具。位流解析、预测恢复、声道去相关、校验、元数据、Ogg 解复用和 Ogg 封装均由 MoonBit 实现。核心不调用 libFLAC、FFmpeg、FFI 或浏览器内建音频解码器；libFLAC 仅供外部验证脚本生成和解码参考数据。新增编码器输出原生 FLAC，同样不依赖外部编码器；其独立验收进度单独记录在 [编码器台账](docs/ENCODER-PROPOSAL.md)。

## 功能

本地交付状态（2026-10-01）：稳定版本 C95 已通过当前 Windows/WSL、长流/RF64、持续压力与浏览器检查，功能交付独立终审已通过。**超过 libFLAC 的性能要求仍未达标**；详见[当前验收状态与限制](docs/ACCEPTANCE.md#current-local-delivery-2026-10-01)。

支持 4–32-bit、1–8 声道、1–1,048,575 Hz，固定/可变块，16–65,535 样本块和更短的末帧；支持 constant、verbatim、0–4 阶 fixed、1–32 阶 LPC、Rice/Rice2、escape 和 wasted bits。解码预测与立体声还原使用 Int64，覆盖 32-bit 音频的 33-bit side channel，并检查还原后的数值范围。编码预测保持精确整数语义；部分 LPC 内核在已证明可精确表示的数值范围内使用 Double 运算。

完整解析 STREAMINFO、PADDING、APPLICATION、SEEKTABLE、VORBIS_COMMENT、CUESHEET、PICTURE；未知块类型 7–126 原样保留，127 拒绝。帧输出前检查 CRC8/CRC16，流或 Ogg 链接结束时检查可用的 STREAMINFO MD5，未提供 MD5 时明确报告。支持原生 FLAC、Ogg FLAC 与串接链接，整文件和增量逐帧 API、原生帧索引、精确样本区间裁剪、原始 PCM、WAV、WAVE_FORMAT_EXTENSIBLE、RF64；新增原生帧到 Ogg FLAC 的封装，以及整段 PCM 到 Ogg 的便捷输出。

实现依据 [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html) 与有效勘误 [8256](https://www.rfc-editor.org/errata/eid8256)、[8810](https://www.rfc-editor.org/errata/eid8810)。合法的逐帧格式变化由帧属性表达；单个 WAV 输出要求格式一致。采样率为零的非音频数据可以解码，但不能作为普通 WAV 音频播放/导出。具体证据见功能验收矩阵。

## 本地构建

准备 [MoonBit](https://www.moonbitlang.com/download/)、本机 C 工具链、Node.js、Python 3。本地开发工具链为 `moon 0.1.20260827`。

精确复现编译器时，从 `https://cli.moonbitlang.com/install/unix.sh` 下载官方脚本并执行 `bash install-moonbit.sh '0.10.16+b1a0e846e'`。CI 固定此编译器/core 版本；`moon` 构建工具使用独立版本编号。

```sh
moon update
moon fmt --check
moon check --target native
moon test --target native
moon build --target native
moon check --target js
moon test --target js
moon build --target js
moon check --target wasm-gc
moon test --target wasm-gc
moon build --target wasm-gc
moon run examples/stream --target native
moon run examples/ogg --target native
```

CLI 面向 native，浏览器桥接支持 JavaScript 与 wasm-gc，根库支持三个目标。CI 配置位于 `.github/workflows/ci.yml`；本地通过不代表远端 CI 已运行。

## CLI

```sh
moon run cmd/moonflac --target native -- info input.flac --json
moon run cmd/moonflac --target native -- verify input.flac
moon run cmd/moonflac --target native -- decode input.flac output.wav
moon run cmd/moonflac --target native -- decode input.flac output.pcm --raw
moon run cmd/moonflac --target native -- decode input.flac excerpt.wav --start 48000 --end 96000
moon run cmd/moonflac --target native -- decode input.flac output.wav --rf64
moon run cmd/moonflac --target native -- encode input.wav output.flac
moon run cmd/moonflac --target native -- encode input.rf64 output.flac --effort 8 --variable-block
moon run cmd/moonflac --target native -- encode input.pcm output.flac --raw --sample-rate 48000 --channels 6 --bits 24 --channel-mask 0x060f
moon run cmd/moonflac --target native -- ogg output.flac output.oga
```

区间是从零开始、右端不包含的 `[start,end)`，样本数按每声道计算。原始 PCM 为有符号、小端、交错排列，以 `ceil(bits/8)` 字节符号扩展存储；WAV 有效位左对齐，8-bit 容器使用无符号表示。高位深和多声道使用 extensible 格式，超过 RIFF 大小范围自动采用 RF64，也可以显式指定。

退出码：0 成功、2 参数错误、3 输入/编解码失败、4 文件 I/O 失败。诊断包含可用的位置。CLI 以 64 KiB 分块读入并逐帧消费；`info` 与 `verify` 都验证完整输入。输出文件须支持定位；已有文件会覆盖，失败时可能留下不完整输出。

所有命令支持 `--max-buffer BYTES`，默认 33,554,432，允许范围 4–2,147,483,647。异常大的合法语料可使用 `verify large.flac --max-buffer 134217728`。触及默认资源预算会明确报错，不代表该编码模式不受支持。

`encode` 默认读取整数 PCM RIFF WAVE/RF64，支持 extensible 有效位深和声道掩码。原始 PCM 必须同时指定 `--sample-rate`、`--channels`、`--bits`，使用上述有符号小端表示；不接收浮点 WAV 或其他原始字节序。`--block-size` 默认 4096，范围 16–65535；`--effort` 默认 5，范围 0–8；`--variable-block` 启用自适应分块。原始输入采样率为零时须加 `--non-audio`。WAV 声道掩码默认保留，显式 `--channel-mask HEX` 可以覆盖；其他 WAV 块被跳过，不自动转换为 FLAC 标签。CLI 在结束时回写 STREAMINFO；编码时 `--max-buffer` 控制元数据预算，PCM 读入暂存仍为 64 KiB。

## Ogg FLAC 输出

`ogg_from_flac(native)` 把一份完整的原生 FLAC 转换为单个 Ogg FLAC 逻辑流。它先验证原生帧索引，保留 STREAMINFO 和元数据；源文件没有元数据包时补一个空 Vorbis 注释包，并写出带 CRC、continuation 和 granule 的 Ogg 页。`encode_ogg_pcm(samples, config)` 是整段 PCM 到 Ogg 的便捷路径；原生流式编码器仍单独受块大小约束。

```sh
moonflac ogg recording.flac recording.oga
moonflac info recording.oga
```

`ogg` 命令会把原生输入整体读入内存，适合普通文件而非数十 GB 录音；输入本身无法驻留内存时，应使用库的原生编码流式接口并自行消费输出。`--serial HEX` 可覆盖默认逻辑流序号 `0x4d464c43`；`--vendor NAME` 只在源文件没有 Vorbis 注释时设置生成的 vendor 字符串。[`examples/ogg`](examples/ogg/main.mbt) 是三目标可运行的 PCM→Ogg 往返示例。

## 原生 FLAC 编码 API

`encode_pcm(samples, EncoderConfig::new(format))` 接收交错排列、未经左对齐的有符号 `Array[Int]`，返回已填写最终 STREAMINFO 的原生 FLAC。`PcmFormat` 指定采样率、声道数和有效位深；覆盖 4–32-bit、1–8 声道和规范采样率范围，越界样本报错而不裁剪。配置还包括块大小、可变分块、effort、可选声道掩码、原始元数据块、非音频模式和元数据预算，后者默认 64 MiB。

长流使用 `Encoder::new`、`next`、`push`、`finish`：先消费初始 `EncodedBytes` 头，再提供 PCM。`push` 返回接受的**单个声道标量数量**，不足部分须在排空输出后重试；内部保留 PCM 不超过 `block_size * channels` 个标量。`finish` 拒绝空输入和不完整声道组，之后继续消费至 `EncoderDone`。完成摘要提供 PCM MD5 和等长 `final_header`；可定位输出用它替换初始头，不可定位输出可保留合法的零值未知总数/MD5。整文件 `encode_pcm` 自动完成替换。

元数据块及声道掩码可由库 API 保留；掩码与已提供注释冲突时拒绝。用户提供的 SEEKTABLE 必须与实际编码帧的样本、偏移和块大小相符，否则报错。effort 0 使用 constant/verbatim；更高等级搜索 fixed、LPC、Rice/Rice2/escape 和立体声分配。LPC 浮点分析只用于提出候选，整数预测与残差计算决定无损正确性。各等级搜索范围及完整流式契约见 [API 文档](docs/API.md#native-flac-encoding)。

当前 effort 8 使用保守成本下界剪枝，保持可改善当前结果的候选的精确残差分区成本。至多 256 个样本的块和细分区情况保留完整 LPC 池；较大的不规则块使用分层整数残差探测，按 Rice/Rice2/escape 成本排序；较大的规则块使用带适用性检查的协方差估计，不适用时退回残差位宽采样。排序搜索精确评估四个完整残差合法的候选，非法候选由后续模型补位。这些排名是启发式策略，文件大小变化取决于输入，声明集合的预算不代表任意输入保证；整数 PCM 仍逐样本无损。新增的六个正弦波案例中，一例比固定质量基线大约 39%；[冻结复现文件](validation/evidence/supplemental-quality-stage18/README-v2.md)保留了这一既有短板。超过 libFLAC 的性能目标仍未完成。


编码器功能基线验收已完成：三个后端各 **103/103** 项目测试；**328** 个原生独立案例、跨后端共 **828** 条流、**137** 种编码表示通过参考验证；全部 **75** 个有效语料文件完整重编码为 **84** 条同格式流，**50,363,649** 个样本帧精确一致。见[编码器台账](docs/ENCODER-PROPOSAL.md)、[独立证据](validation/encoder/README.md)及[可运行编码示例](examples/encode/main.mbt)。此前[搜索优化实测](docs/PERFORMANCE.md)包含位流不变及实际 Windows/WSL 验证；当前数值分析可能改变压缩字节，仍保持 PCM 无损。持续压力门槛单列于[验收台账](docs/ACCEPTANCE.md)。高 effort 搜索仍慢于 libFLAC。

## API 与浏览器

`decode(bytes)` 返回单个流的完整音频，`decode_chained(bytes)` 返回 Ogg 各链接。长流使用 `Decoder::new`、`push`、`next`、`finish`。`push` 返回接受的前缀长度，未接受部分必须重试；`NeedInput` 不表示结束。调用 `finish` 后继续消费，直至 `Done` 或错误。输出 PCM 属于调用者；可在消费后释放，而不累积整个录音。可运行的 [流式示例](examples/stream/main.mbt) 与 [API 文档](docs/API.md) 给出了完整契约。

```sh
node playground/build.mjs
node playground/serve.mjs
```

打开 [本地 Playground](http://127.0.0.1:8080)，选择或拖放文件，选择 JavaScript 或 WebAssembly GC 后端，查看元数据/波形，播放、暂停、定位并导出 WAV。对应的 MoonBit 编译产物在 Worker 中解码；切换后端会重新解码同一文件，Web Audio 只接收 PCM。页面分别显示解码/数据传输与后端加载/编译耗时，不支持 wasm-gc 的浏览器会明确报错。播放的 Float32 与设备重采样可能改变精度，整数 WAV 导出保留源精度。大文件限制、取消行为与浏览器差异见 [Playground 说明](playground/README.md)。

## 独立验证与边界

Ubuntu 安装 `flac libflac-dev`，Windows 使用 `scripts/prepare-validation.ps1`。执行 `python scripts/validate.py generate` 生成经 libFLAC 独立验证的参考样本，再执行 `compare --cli <本机CLI路径> --corpus generated`。`scripts/fetch-corpus.py` 获取并记录公共语料版本；普通文件使用 `compare --corpus subset`，uncommon 中的原始帧流和属性变化输入使用 `frames --cli <validation/runner路径> --corpus uncommon`。必须按 [公共语料](https://github.com/ietf-wg-cellar/flac-test-files) 各组 README 区分正常和 faulty 输入。参数/PCM 位于 `validation/cache/generated`，结果位于 `validation/results`；[性能文档](docs/PERFORMANCE.md) 说明测量范围。

编码器扩展前保留的解码验收基线：生成参考 **245/245**、subset **64/64**、uncommon 逐帧对照 **11/11** 全部一致，faulty **11/11** 明确拒绝。subset 55 文件为 87.3 MB，其中元数据为 82.2 MB，对照时使用 `--max-buffer 134217728 --timeout 180`。三个目标的 check/build 与项目 **67/67** 测试通过，其中独立 golden 包各 **14/14** 通过。两种浏览器后端均经过真实 Chromium 交互验证，切换后导出 WAV 字节一致。[保留的证据](validation/evidence/README.md) 记录版本、哈希和复现命令；不声称远端 CI 已执行。

本期 Ogg 输出增量（2026-11-02）：native、JavaScript、wasm-gc 各 **196/196** 项目测试通过，其中新增 3 个 Ogg 封装测试（元数据/PCM 往返、跨页帧续接、非法输入）。CLI 合同测试还会用独立 libFLAC 验证 Ogg 输出并逐字节比较解码 PCM。人工 libFLAC 检查覆盖 16/24/32-bit 与 2/6/8 声道；4-bit Ogg 输出通过 `flac -t`，但 libFLAC 的 raw 输出模式不接受 4-bit 样本，未做逐字节比较。

编码器输出原生 FLAC，并可把已完成的原生帧封装为 Ogg FLAC；每次调用输出一个逻辑流，CLI 当前会把输入整体读入内存。其他音频编码、MP4/Matroska 容器、浏览器音频编辑/AudioWorklet 播放及系统播放器后端不在范围内。原生输入支持可复用字节索引；Ogg 区间导出顺序解复用。这些容器/应用边界不删减 FLAC 帧编码能力。异常大的合法输入可提高资源限制，触限时明确报错。

Apache-2.0，见 [许可证](LICENSE) 和 [第三方来源](THIRD_PARTY.md)。当前检出即公开提交版本；仓库与 CI 记录见 [HACKATHON.md](HACKATHON.md)。

后续 effort-8 优化的固定集合中位耗时合计下降 **核心51.6% / CLI 51.8%**，输出位流不变；Windows 与 WSL2 三后端各103/103通过。本轮本地验证及独立审核均已通过。静音和最大块未显示明确收益，高 effort 仍慢于 libFLAC；详见[配对测量及参考工具限制](docs/PERFORMANCE.md)。

第7版速度优先优化实测：原12项固定集合 **CLI 再快4.83倍**（49.10 → 10.17秒）、**核心快3.60倍**，CLI 耗时约为同轮 libFLAC `-8` 的 **8.71倍**。完整文件总大小增加0.0159%；所有声明的质量集合满足总计+1%、单例+3%预算。Windows/WSL 三后端各 **121/121** 通过。这是指定集合的实测约束，libFLAC 仍更快。[完整测量与失败记录](docs/SPEED-FIRST-EVIDENCE.md)及[验收记录](docs/ACCEPTANCE.md)区分当前和历史数据；最终独立复核已通过，全部确认问题已关闭。


当前 `faster-than-libflac-20260929` 目标严于第7版目标。C95 已通过三个后端各 **194/194** 测试、220 个独立案例及 16 份长流 CLI/core 输出，满足声明集合的固定质量预算，且已通过独立审核。相对 C83 的直接配对测量中，核心总耗时降低约 1.55%，CLI 降低约 2.40%，所有退化案例均保留。保留的历史单轮正常 libFLAC-8 诊断为 **核心 1.71 倍 / CLI 1.45 倍耗时**，目标尚未完成。本轮已实跑通过当前产物的 Windows/WSL、长流与持续压力门槛；macOS 和独立 Linux 硬件未测试。本次合并功能交付独立终审已通过；性能胜出及最终重复区组仍未完成。见[当前契约](docs/ACCEPTANCE.md)和[最新测量](docs/PERFORMANCE.md#selected-triangular-variance-implementation-c95)；C4 历史证据保留于 `faster-than-libflac-stage1.json`。
