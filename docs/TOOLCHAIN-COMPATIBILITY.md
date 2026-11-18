# 工具链兼容验证（2026-11-11）

按 MoonBit 开源大赛组委会统一维护提醒，使用官方当前发布工具链重新验证。本仓库不在邮件点名的三个项目内，但为保持本机所有项目工具链一致，一并升级。

## 实际工具链（`moon version --all`）

```
moon     0.1.20261117 (eb64713 2026-11-17)
moonc    v0.10.21+06da1ed44 (2026-11-16)
moonrun  0.1.20261117 (eb64713 2026-11-17)
```

CI 固定版本：`0.10.21+06da1ed44`。

## 标准入口验证结果

| 项目 | 结果 |
|---|---|
| `moon fmt --check` | 通过 |
| `moon check --target native/js/wasm-gc` | 0 errors |
| `moon test --target native` | 197/197 |
| `moon test --target js` | 197/197 |
| `moon test --target wasm-gc` | 197/197 |
| `python cmd/test_cli.py`（libFLAC 1.5.0 对照） | 通过，含 Ogg mux 与 PCM 逐字节比较 |

CI 覆盖三后端 check/test/build、示例、CLI 合同测试、libFLAC PCM 对照与浏览器构建。

## 适配记录

- **旧 API 修复**：0.10.20 移除了 `Int`/`String`/`Array` 等类型的 promoted `value.to_json()` 方法，`cmd/moonflac/main.mbt` 的 `metadata_json` 中 16 处调用改为官方建议的 `Json(value)` 构造形式；`moon check --target native` 从 16 errors 恢复为 0 errors，`info --json` 输出不变。
- **旧语法迁移**：14 处 `} derive(...)` 改为 `#derive(...)` 前缀形式，`moon fmt --check` 与 `moon info` 接口漂移检查通过。

## 发布

`0717lee/moonflac@0.2.3` 包含上述 API 修复，避免旧包在 0.10.21 下从源码编译失败。

## 0.10.21 升级（2026-11-18）

- 官方发布 `moonc 0.10.21+06da1ed44`，CI、README、HACKATHON 与本文档同步固定。
- 0.10.21 移除了 trait 方法的隐式提升：`FlacError` 显式 `pub extend ... with Show::{to_string, output}`，`browser/bridge.mbt` 4 处 `.to_string()` 改为 `Show::to_string(x)`；`pkg.generated.mbti` 重新生成。
- 三目标 `moon check` 0 errors、测试 197/197；`moon fmt --check` 与 CLI 合同测试通过。
