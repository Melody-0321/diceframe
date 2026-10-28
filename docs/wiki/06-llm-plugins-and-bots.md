# 06 LLM、插件与 Bot

> 核心目录：[src/llm/](../../src/llm/) · [src/plugin_host/](../../src/plugin_host/) · [src/plugin_sdk/](../../src/plugin_sdk/) · [src/bots/](../../src/bots/) · [src/imagegen/](../../src/imagegen/) · [src/tts/](../../src/tts/) · [src/asr/](../../src/asr/)

## 1. LLM 子系统

### 1.1 模块边界

| 文件 | 职责 |
|---|---|
| `client.py` | 多供应商异步客户端、重试、fallback、流式、工具调用 |
| `openai_transport.py` | OpenAI-compatible 传输与能力学习 |
| `context_builder.py` | 上下文预算、历史压缩、状态/世界/世界书投影 |
| `parser.py` | 从模型输出中提取叙事与 JSON |
| `protocol.py` | 结构化标签协议解析与防泄漏 |
| `tools.py` | 工具 schema（如 `dice_checks`） |
| `world_prompt.py` | WorldState / 合法性 / 事件提示块 |
| `combat_choice.py` | 托管战斗选择 |
| `seat_policy.py` | 席位生成运行时 |
| `failure.py` | 安全失败原因 |

### 1.2 `LLMClient`

```python
@dataclass
class ProviderConfig:
    provider_name: str
    base_url: str
    api_key: str
    model_name: str
    api_format: str = "openai"   # openai | anthropic
    fallback: bool = False
```

关键方法：

| 方法 | 作用 |
|---|---|
| `call(...)` | 非流式调用，返回 `LLMResponse` |
| `call_stream(...)` | 流式调用 |
| `call_tools(...)` | 工具规划调用，返回 `LLMToolResponse` |
| `close()` | 关闭连接 |

行为：

- 按 provider 顺序尝试，失败降级到 fallback；
- 支持 OpenAI-compatible 与 Anthropic Messages；
- 输出截断抛 `OutputTruncatedError`，按 `length_retry_budgets(...)` 提升 token 档位重试；
- 推理内容（reasoning）在非流式与流式路径都会被剥离；
- 工具调用有独立校验，不把模型参数直接当权威。

### 1.3 上下文构建

[context_builder.py](../../src/llm/context_builder.py) 的 `build_context(...)`：

```python
async def build_context(
    instance, gm_prompt_filled, lorebook_entries, player_message,
    memory_store=None, platform="", provider_name="",
    lorebook_budget=0, history_override=None,
    directives_text="", overreach_text="",
    world_state_text="", world_legality_text="", world_events_text="",
    state_view=None, authoritative_events_text="",
    context_recent_rounds=0, scene_objective_view=None,
) -> str
```

预算策略：

- 按模型上下文窗口估算 `max_total`；
- 按比例分配给 system prompt / game state / history / lorebook / player message 等；
- 超窗时从低优先级段落开始收缩，必要时丢弃最旧回合；
- `lore_char_budget(...)` 是世界书部分唯一的上下文窗口权威；
- `context_recent_rounds` 只截取近期日志视图，不修改已保存历史。

玩家安全上下文：`build_player_safe_context(...)` 只暴露玩家可见状态与世界书条目。

### 1.4 提示词组装

[prompt_composer.py](../../src/commands/prompt_composer.py) 的 `PromptComposer`：

| 方法 | 作用 |
|---|---|
| `load_gm_prompt(...)` | 加载 GM 系统提示词 |
| `load_rule_context(...)` | 规则片段 |
| `load_swipe_rule_context(...)` | swipe 专用规则 |
| `compose_gm_prompt(...)` | 填充占位符与规则上下文 |
| `build_user_context(...)` | 组装玩家上下文 |
| `build_player_safe_context(...)` | 玩家安全上下文 |
| `scene_objective_view(...)` / `scene_context_text(...)` | 当前场景目标 |

### 1.5 输出解析与协议

- 模型被要求先输出叙事，再输出末尾 ```json``` 块；
- `parse_llm_response(raw)` 解析出 `narration` / `state_update` / `memory_delta` / `info_asymmetry` / `plot_update`；
- JSON 解析失败时降级为 `is_narration_only`，并触发协议修复/重试；
- `protocol.py` 处理结构化标签行，防止内部标签泄漏到玩家叙事；
- `sanitize_narration(...)` 清理元文本、内部标题和协议残留；
- `strip_reasoning_from_content(...)` 清理推理内容。

### 1.6 工具调用

`src/llm/tools.py` 定义工具 schema，例如 `dice_checks`：

```text
模型可以提出：谁需要检定、属性/技能、目标
模型不能提出：最终骰值、合法 actor 结论、HP/余额写入
```

服务端随后执行 `normalize_check_specs(...)`、规则校验与掷骰。

### 1.7 Stale Fence 与安全

LLM 返回后，提交前必须校验：

```text
run_id 未变化
round 未变化
控制权 revision 未变化
状态仍允许写入
经济/规则模块未产生阻塞
```

否则丢弃结果，不写入权威状态。

### 1.8 Player-safe Q&A

`build_player_safe_context(...)` 与可见性过滤确保：

- GM 私密事实、私聊、隐藏世界书条目不进入玩家回答；
- KP 问答（`kp_questions.py`）只使用玩家可见信息；
- Bot 输出同样经过可见性投影。

---

## 2. DF Agent（应用智能体）

实现：[src/webui/services/assistant_agent.py](../../src/webui/services/assistant_agent.py) 及 `assistant_*` 服务。

特征：

- owner-only；
- 支持建议 / 计划 / 执行模式；
- 工具调用前需要授权与确认；
- 支持草稿、review、confirm、resume；
- 工具覆盖内容、世界书、设置、插件、玩法、恢复等域；
- 不绕过权限与服务端校验。

相关入口：

```text
POST /api/assistant/agent/plan
POST /api/assistant/agent/run
POST /api/assistant/agent/confirm
POST /api/assistant/agent/resume
POST /api/assistant/agent/review
GET  /api/assistant/agent/session/{session_id}
```

---

## 3. 媒体能力

| 能力 | 目录 | 关键类 / 文件 |
|---|---|---|
| 图像生成 | `src/imagegen/` | `ImageGenerationService`、`providers.py`、`assets.py`、`storyboards.py` |
| TTS | `src/tts/` | `SpeechService`、`providers.py`、`profile_store.py` |
| ASR | `src/asr/` | `AsrService`、`providers.py` |

共同原则：

- 资产文件与游戏状态分离；
- 游戏状态只保存引用（如 `scene_image`）；
- 生成失败不回滚已经提交的回合；
- 远端能力需要有效的 provider 引用；缺失时保持未配置或停用。

TTS 特例：`browser`、`edge-tts` 无需 provider 引用；本地服务商允许空密钥。

---

## 4. 插件宿主（PluginHost）

### 4.1 设计

[src/plugin_host/host.py](../../src/plugin_host/host.py) 的 `PluginHost` 负责：

- 发现与加载 `plugin.json`；
- 校验 manifest、权限、entrypoint、schema；
- 启停子进程 / RPC 进程；
- 注入配置、密钥、`TRPG_API_BASE`、AI provider 环境；
- 注册 contributions（内容、主题、音色、地图等）；
- 市场安装、更新、镜像、卸载；
- 包校验与路径安全；
- 崩溃监控与退避重启。

### 4.2 插件类型

[src/plugin_host/support.py](../../src/plugin_host/support.py)：

| 类型 | 进程模式 | 能力 |
|---|---|---|
| `content-pack` | static | 规则、世界、角色、NPC、道具、法术、职业、地图、冒险包 |
| `theme` | static | 主题颜色变量 |
| `voice-pack` | static | TTS 音色预设与参考音频 |
| `tool` | RPC | 结构化工具调用 |
| `provider` | RPC | 外部服务能力（如图像生成） |
| `bot-extension` | RPC | Bot Bridge 命令、消息处理、渲染 |
| `channel-adapter` | plain subprocess | 连接聊天平台并调用 DiceFrame HTTP API |
| `import-export` | none | 预留，未接入 |

### 4.3 Manifest

示例：[plugins/examples/echo-tool/plugin.json](../../plugins/examples/echo-tool/plugin.json)

```json
{
  "schema_version": 1,
  "id": "echo-tool",
  "name": "Echo Tool",
  "version": "0.1.0",
  "plugin_type": "tool",
  "entrypoint": ["{python}", "{plugin_dir}/main.py"],
  "config_schema": "config.schema.json",
  "capabilities": ["tool.echo"],
  "permissions": ["process.spawn", "plugin.config", "plugin.data", "tool.execute"],
  "docs": "README_CN.md"
}
```

关键字段：

| 字段 | 说明 |
|---|---|
| `schema_version` | manifest 版本 |
| `id` | canonical 插件 ID |
| `plugin_type` | 决定进程模式与能力 |
| `entrypoint` | 启动命令模板 |
| `config_schema` | 配置 JSON Schema |
| `capabilities` | 声明能力 |
| `permissions` | 请求权限 |
| `contributes` | 静态贡献路径（content-pack / theme / voice-pack） |
| `min_app_version` | 仅提示，不阻断加载 |

### 4.4 权限

常见权限：

```text
process.spawn
plugin.config
plugin.data
tool.execute
network.client
diceframe.http
content.read / content.import
theme.tokens
voice.assets
bot.extend
```

宿主会校验 manifest 权限与运行时 schema 权限，拒绝未声明的敏感操作。

### 4.5 进程与 RPC

- `content-pack` / `theme` / `voice-pack` 不启动进程；
- `tool` / `provider` / `bot-extension` 通过受限 JSON-RPC（`JsonRpcStdioClient`）通信；
- `channel-adapter` 是普通子进程，通过 `TRPG_API_BASE` 调用 HTTP API；
- 子进程环境包含配置、密钥与 AI provider 信息，不暴露核心对象。

### 4.6 SDK

[src/plugin_sdk/](../../src/plugin_sdk/)：

| 模块 | 用途 |
|---|---|
| `tool_runtime.py` | `ToolRuntime`，`@runtime.tool(...)` 注册工具 |
| `provider_runtime.py` | `ProviderRuntime`，`@runtime.capability(...)` 注册能力 |
| `bridge_runtime.py` | `BridgeExtensionRuntime`，声明 `before_message` / `after_result` / `render` |
| `contracts.py` | 共享 descriptor 类型 |

示例工具：

```python
from src.plugin_sdk import ToolRuntime

runtime = ToolRuntime()

@runtime.tool(name="echo", input_schema={...})
def echo(arguments: dict, context: dict) -> dict:
    return {"content": [{"type": "text", "text": arguments["text"]}]}

if __name__ == "__main__":
    runtime.run()
```

### 4.7 安装、市场与镜像

- `install_from_zip(...)`：本地包安装；
- `install_from_marketplace(...)` / `update_from_marketplace(...)`：市场安装与更新；
- `marketplace.py`：市场索引；
- `mirrors.py`：镜像管理；
- `package_limits.py`：包大小限制；
- `_extract_zip(...)` / `_ensure_inside(...)`：路径穿越防护；
- 安装前校验 manifest、权限、类型、内容和绑定的存档。

### 4.8 生命周期

```text
discover()
  → load manifest / schema
  → validate package
  → register contributions
  → start_enabled()
  → monitor process
  → crash → backoff restart
  → stop() / uninstall()
```

卸载时按类型清理内容与数据；绑定了存档的插件可能被保护，避免破坏已绑定对局。

---

## 5. Bot 与渠道路由

### 5.1 组成

| 位置 | 职责 |
|---|---|
| `src/webui/routes/bot.py` | Bot HTTP 端点 |
| `src/webui/services/bot_access.py` | token 校验 |
| `src/webui/services/bot_extensions.py` | bridge extension 应用 |
| `src/bots/bridge_core/service.py` | 消息 → 命令 → DiceFrame API |
| `src/bots/bridge_core/client.py` | DiceFrame HTTP 客户端 |
| `presenters.py` | 文本/卡片/图片呈现 |
| `card_renderer.py` | 卡片渲染（需要 CJK 字体） |
| `commands.py` / `triggers.py` | 命令解析与触发 |
| `store.py` | 绑定关系与群配置 |

### 5.2 流程

```text
QQ / NapCat 群消息
  → channel-adapter 插件
  → DiceFrame bot HTTP API
  → BridgeService.handle(message)
  → 命令解析 / 绑定校验 / actor 解析
  → 调用 action / advance / luck / payment / status 等 API
  → 可见性投影 + presenters
  → 文本 / 卡片 / 图片回复
```

### 5.3 安全

- Bot token 由宿主生成或从 `TRPG_BOT_TOKEN` 读取；
- 绑定游戏需要 bind token；
- Bot 只能代表合法 actor 调用 API，不能绕过房间/游戏权限；
- 私聊、GM 私密事实不会进入公开群消息；
- 卡片渲染路径限制在允许目录内。

---

## 6. 关键类与函数速查

| 符号 | 位置 | 说明 |
|---|---|---|
| `LLMClient` | [llm/client.py](../../src/llm/client.py) | 多供应商客户端 |
| `ProviderConfig` / `LLMResponse` | 同上 | 供应配置与响应 |
| `build_context` | [llm/context_builder.py](../../src/llm/context_builder.py) | 上下文组装 |
| `parse_llm_response` | [llm/parser.py](../../src/llm/parser.py) | 输出解析 |
| `PromptComposer` | [commands/prompt_composer.py](../../src/commands/prompt_composer.py) | 提示词 |
| `PluginHost` | [plugin_host/host.py](../../src/plugin_host/host.py) | 插件生命周期 |
| `PluginRuntime` | [plugin_host/models.py](../../src/plugin_host/models.py) | 运行时状态 |
| `PluginManifest` | [plugin_host/contracts.py](../../src/plugin_host/contracts.py) | manifest 契约 |
| `ToolRuntime` | [plugin_sdk/tool_runtime.py](../../src/plugin_sdk/tool_runtime.py) | 工具 SDK |
| `DiceFrameBridgeService` | [bots/bridge_core/service.py](../../src/bots/bridge_core/service.py) | Bot 消息处理 |
| `DiceFrameClient` | [bots/bridge_core/client.py](../../src/bots/bridge_core/client.py) | Bot HTTP 客户端 |
| `AgentRuntime` | [webui/services/assistant_agent.py](../../src/webui/services/assistant_agent.py) | DF Agent |

---

## 7. 扩展检查清单

### 新增 LLM 能力

- [ ] 是否只是新的 prompt / tool schema，而不是绕过服务端校验？
- [ ] 是否处理输出截断、解析失败、reasoning 泄漏？
- [ ] 是否在 stale fence 之后才写入状态？
- [ ] 是否更新 context 预算与玩家安全投影？

### 新增插件

- [ ] 选择现有 plugin type，还是确实需要新 type？
- [ ] manifest 权限最小化？
- [ ] 是否有包校验、路径安全、超时与清理测试？
- [ ] 是否通过 SDK 注册，而不是自建协议？
- [ ] content-pack 是否声明 canonical ID 与 locale？

### 新增渠道

- [ ] 是否作为 `channel-adapter`，只调用 HTTP API？
- [ ] 是否遵守 actor / room / game 权限？
- [ ] 输出是否经过可见性投影与长度限制？
