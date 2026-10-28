# DiceFrame Code Wiki

本目录是 DiceFrame 的**代码级 Wiki**：面向准备阅读源码、修复缺陷或扩展能力的开发者，用一套连续文档回答四个问题：

1. 这个项目由哪些部分组成？
2. 每个模块拥有什么职责与权威（authority）？
3. 关键类、函数和依赖关系在哪里？
4. 如何在本机、Docker 与发布环境中运行和验证？

> **文档基线**
>
> - 仓库：`diceframe`
> - 分支：`main`
> - Commit：`03c6da6ef2237aa4f56690b465b684caf03190be`
> - 应用版本：`3.0.3`（`src/version.py`）
> - GameInstance persisted schema：`47`（`src/migrations/instance.py`）
> - Lorebook SQLite schema：`12`
> - 核验日期：2026-10-28
>
> 本 Wiki 是**阅读导航与实现说明**，不新增契约。权威事实仍以当前源码、[架构文档](../ARCHITECTURE_CN.md)、[工程规则](../ENGINEERING_RULES.md) 和 [ADR](../adr/README.md) 为准；两者冲突时以源码与架构文档为准。

---

## 文档地图

| 文档 | 内容 | 适合谁 |
|---|---|---|
| [01 项目总览](01-project-overview.md) | 项目定位、核心能力、技术栈、仓库地图、运行时拓扑 | 所有人，第一次进仓库 |
| [02 架构与权威模型](02-architecture-and-authority.md) | 分层、依赖方向、authority、请求链路、并发与模块钩子 | 需要改核心逻辑的人 |
| [03 后端运行时](03-backend-runtime.md) | 启动序列、Composition Root、aiohttp、WebAPI、routes/services、SSE、访问控制 | 后端开发者 |
| [04 游戏引擎与回合](04-game-engine-and-turns.md) | GameInstance、GameHandler、回合流水线、检定、WorldState、经济、记忆 outbox | 游戏逻辑开发者 |
| [05 规则集与内容](05-rulesets-and-content.md) | Legacy RuleSystem、Ruleset Runtime、D&D 2024、冒险包、Content V2、世界书、记忆 | 规则/内容开发者 |
| [06 LLM、插件与 Bot](06-llm-plugins-and-bots.md) | LLM 客户端、上下文预算、协议解析、插件宿主、SDK、Bot 桥接 | AI/插件/渠道开发者 |
| [07 前端](07-frontend.md) | Vue 应用结构、路由、API 客户端、SSE、Play 页面、能力门控 | 前端开发者 |
| [08 持久化与数据](08-persistence-and-data.md) | 数据目录、存档 codec、schema 迁移、SQLite、回滚与 outbox | 涉及存档/迁移的人 |
| [09 运行、测试与部署](09-run-test-deploy.md) | 本地运行、环境变量、Docker、Portable、测试与 CI | 需要跑起来/发版的人 |
| [10 关键类与接口速查](10-key-reference.md) | 符号速查、HTTP 路由分组、钩子点、模块状态、术语表 | 日常查代码 |

---

## 推荐阅读路径

### 第一次接触项目

```text
01 项目总览
  → 02 架构与权威模型
  → 09 运行、测试与部署（先跑起来）
  → 03 后端运行时
  → 04 游戏引擎与回合
```

### 修一个“玩家行动后没有推进”的 bug

```text
03 后端运行时（route → WebAPI → service）
  → 04 游戏引擎与回合（turns.submit_action → GameHandler → RoundProcessor）
  → 08 持久化与数据（run_id / 锁 / 回滚）
  → tests/test_turn_service.py、test_action_run_pipeline.py
```

### 新增规则集或规则能力

```text
05 规则集与内容（RulesetRuntime / capabilities / bundle）
  → 02 架构与权威模型（不要污染 generic engine）
  → 10 关键类与接口速查
```

### 新增前端页面或玩法面板

```text
07 前端（router / api client / capability gating）
  → 03 后端运行时（对应 route/service）
  → 02 架构与权威模型（服务端必须重新校验）
```

---

## 三条最重要的架构原则

1. **LLM 不是状态权威。** LLM 负责叙事、理解与候选计划；HP、余额、法术位、战斗顺序、权限、存档 identity 必须由服务端规则 runtime / reducer 结算并持久化。
2. **每一类状态只有一个 owner。** 例如 `GameInstance` 拥有单局聚合状态，`WorldState` 拥有世界事实与逻辑时钟，`LorebookStore` 拥有世界书内容，`PluginHost` 拥有插件进程与配置。表现层可以投影，但不能复制出第二套权威。
3. **跨边界用显式契约。** 新能力优先通过 ruleset capability、plugin capability、module hook、service 接口扩展，而不是在通用路径增加具体规则分支。

---

## 术语表

| 术语 | 含义 |
|---|---|
| `game_key` | 一局游戏的槽位标识，通常为 `(platform, target_id, account_id)` |
| `run_id` | 同一 `game_key` 下的一次运行实例；重开后变化，用于拒绝过期写入 |
| Authority | 某类状态的最终决定权；通常对应一个明确的 owner 模块 |
| Projection | 从权威状态派生给 UI/LLM 的只读视图，不反向成为权威 |
| Ruleset Runtime | 版本化规则运行时，如 `core:legacy`、`core:dnd2024` |
| Capability | 规则集或插件显式声明的可选能力开关 |
| Module Hook | 核心流程的固定钩子点，能力模块通过注册参与，核心不点名模块 |
| Outbox | 跨存储副作用的待投递记录，用于崩溃/重试/回滚一致性 |
| Lorebook | 世界书：世界设定的结构化条目与检索系统 |
| Adventure Bundle | 冒险包：节点、门控、遭遇、奖励等可绑定内容 |
| Content V2 | 世界/规则/角色等内容的新 canonical identity 与 locale 分离模型 |
| DF Agent | owner-only 的应用智能体，用于文档、草稿与需确认的应用操作 |

---

## 维护规则

代码发生以下变化时，应同步更新对应 Wiki 页面（与 [架构文档维护规则](../ARCHITECTURE_CN.md#57a-给开发者维护这份文档的规则) 一致）：

- Authority owner 改变；
- persisted schema / 迁移语义改变；
- 新增 GameInstance 核心字段或模块槽；
- 新增 ruleset capability / plugin type；
- 新增跨存储 outbox；
- Player Control 或 WorldState 契约改变；
- 主要端到端请求链变化；
- 启动、部署或运行方式改变。

纯样式、文案、按钮位置调整不需要修改本 Wiki。
