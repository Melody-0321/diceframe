# 09 运行、测试与部署

> 入口：[web_server.py](../../web_server.py) · 依赖：[requirements.txt](../../requirements.txt) · 容器：[Dockerfile](../../Dockerfile) · CI：[.github/workflows/ci.yml](../../.github/workflows/ci.yml)

## 1. 环境要求

| 项 | 版本 |
|---|---|
| Python | 3.10+（推荐 3.11；CI 与 Docker 使用 3.11） |
| Node.js | `^20.19.0 || >=22.12.0` |
| npm | `^10.9.0` |
| 操作系统 | Windows / Linux / macOS（Portable 面向 Windows） |
| 模型 | 任意 OpenAI-compatible Chat Completions；可选 Anthropic Messages |

---

## 2. 从源码运行

```bash
# 1. 构建前端
cd frontend-v2
npm ci
npm run build
cd ..

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 启动
python web_server.py
```

打开：

```text
http://localhost:18000
```

首次启动：

1. 进入 **Manage → Settings → Model API → AI Providers**；
2. 添加服务商（名称、API 格式、Base URL、API key、模型目录）；
3. 在 **Model Routing** 指定主模型、fallback、embedding、TTS、ASR、图像生成；
4. 创建对局。

Windows 可使用 [web_ui.bat](../../web_ui.bat)：自动检查依赖，`static-v2/` 缺失时构建前端，然后启动 `web_server.py`。

### 2.1 前端开发模式

```bash
cd frontend-v2
npm ci
npm run dev
```

Vite 将 `/api` 代理到 `http://127.0.0.1:18000`（见 [vite.config.ts](../../frontend-v2/vite.config.ts)）。

### 2.2 独立前端（standalone）

```bash
cd frontend-v2
npm ci
npm run build:standalone
```

产物在 `frontend-v2/dist/`，可部署到 Cloudflare Pages 等静态主机。需要：

- 后端使用 HTTPS（或允许混合内容的环境）；
- 配置 `TRPG_WEB_CORS_ORIGINS`；
- 前端配置后端地址。

---

## 3. 环境变量

### 3.1 数据与安装

| 变量 | 说明 | 默认 |
|---|---|---|
| `TRPG_DATA_DIR` | 数据目录 | `<repo>/data` |
| `TRPG_INSTALL_MODE` | `docker-managed` 等安装模式 | 空 |
| `TRPG_DOCKER_DATA_HOME` | Docker 宿主机数据目录 | `TRPG_DATA_DIR` |
| `TRPG_DOCKER_RUNTIME_ROOT` | 托管 Docker 运行时目录 | — |
| `TRPG_DOCKER_SEED_ARCHIVE` | 初始更新包 | — |
| `TRPG_DOCKER_SEED_CHECKSUM` | 初始包校验 | — |

### 3.2 Web / TLS

| 变量 | 说明 | 默认 |
|---|---|---|
| `TRPG_WEB_HOST` | 主监听地址 | `0.0.0.0` |
| `TRPG_WEB_PORT` | 主端口 | `18000`（Docker 内 `9876`） |
| `TRPG_WEB_HOSTS` | 追加监听地址（逗号/空格分隔） | 空 |
| `TRPG_WEB_HTTP_PORT` | 额外 HTTP 端口 | 空 |
| `TRPG_WEB_HTTPS_PORT` | 额外 HTTPS 端口（需启用 TLS） | 空 |
| `TRPG_TLS_MODE` | `self_signed` / `lets_encrypt` 等 | 空 |
| `TRPG_TLS_IDENTIFIER_TYPE` | 证书标识类型 | 空 |
| `TRPG_TLS_IDENTIFIER` | 域名 / IP | 空 |
| `TRPG_TLS_CONTACT_EMAIL` | ACME 联系邮箱 | 空 |
| `TRPG_TLS_CHALLENGE_TYPE` | ACME challenge 类型 | 空 |
| `TRPG_TLS_ACME_CHALLENGE_PORT` | ACME http-01 端口 | `80` |
| `TRPG_WEB_CORS_ORIGINS` | 允许的前端来源，逗号分隔 | 空 |
| `TRPG_PROXY_URL` | HTTP 代理 | 空 |

### 3.3 访问与 Bot

| 变量 | 说明 |
|---|---|
| `TRPG_ACCESS_TOKEN` | 固定 owner 登录 token；为空则自动生成到 `data/access_token.txt` |
| `TRPG_BOT_TOKEN` | 固定 Bot API token；为空则生成并持久化 |
| `NAPCAT_HOST` / `NAPCAT_PORT` / `NAPCAT_TOKEN` | QQ / NapCat 连接 |
| `DICEFRAME_CONTENT_BASE_URL` | 公共内容镜像地址 |
| `TZ` | 日志时区，默认 `Asia/Shanghai` |

### 3.4 生成参数

| 变量 | 说明 |
|---|---|
| `TRPG_MODEL_REQUEST_TIMEOUT_SECONDS` | 模型请求超时 |
| `TRPG_NARRATIVE_MAX_TOKENS` | 叙事输出上限 |
| `TRPG_CHARACTER_GEN_MAX_TOKENS` | 角色生成上限 |
| `TRPG_SUMMARY_MAX_TOKENS` | 摘要上限 |
| `TRPG_BRIEF_MAX_TOKENS` | 简报上限 |
| `TRPG_ANALYSIS_MAX_TOKENS` | 分析上限 |
| `TRPG_TEXT_GEN_MAX_TOKENS` | 文本生成上限 |
| `TRPG_ASSISTANT_AGENT_MAX_TOKENS` | DF Agent 上限 |

> **不再支持** `TRPG_LLM_*`、`TRPG_EMBEDDING_*`、`TRPG_TTS_*`、`TRPG_ASR_*`、`TRPG_IMAGEGEN_*` 等能力级环境变量。AI 连接统一在 WebUI 配置 `ai_providers` 与 `*_provider_ref`。

---

## 4. Docker

```bash
cp .env.example .env
# 编辑 .env
docker compose pull
docker compose up -d
```

访问：

```text
http://localhost:9876
```

数据挂载：

```yaml
volumes:
  - ./data:/app/data
  - ./plugins:/app/plugins
```

### 4.1 额外端口

| 场景 | 命令 |
|---|---|
| 同时提供 HTTP | `docker compose -f docker-compose.yml -f docker-compose.extra-http-port.yml up -d` |
| 同时提供 HTTPS | `docker compose -f docker-compose.yml -f docker-compose.extra-https-port.yml up -d` |
| Let's Encrypt http-01 | `docker compose -f docker-compose.yml -f docker-compose.acme-challenge.yml up -d` |

容器内监听端口必须同时在 `ports` 发布，否则外部不可达。

### 4.2 镜像阶段

[Dockerfile](../../Dockerfile)：

```text
frontend-build        构建 Vue 前端
update-build          生成应用更新包 zip + sha256
managed-runtime-base  安装 Python 运行时、CJK 字体、启动器
managed-artifact      发布用：使用 CI 产物
runtime               本地 build：使用 update-build 产物
```

启动器：[src/docker_launcher/launcher.py](../../src/docker_launcher/launcher.py)。

### 4.3 托管更新

- 应用更新由 `UpdaterService` 检查与下载；
- 候选版本在独立数据副本上迁移；
- 健康检查失败时旧启动器恢复上一版本；
- Python / 系统运行时变化仍需要新镜像。

---

## 5. Windows Portable

- 发布包：`DiceFrame-vX.Y.Z-windows-portable.zip`；
- 启动器：[src/launcher/](../../src/launcher/)；
- 构建脚本：`scripts/build_portable.py`、`scripts/build_launcher.py`、`scripts/build_release.py`；
- 更新：Settings → About → Version Update；
- 依赖锁定：`requirements-portable.lock`，由 `scripts/validate_portable_lock.py` 校验。

---

## 6. 测试

### 6.1 后端

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q --cov=src --cov-report=term-missing
```

常用范围：

```bash
python -m pytest -q tests/integration/
python -m pytest -q tests/rulesets/
python -m pytest -q tests/architecture/
python -m pytest -q -k "permission or migration"
```

测试约束（[tests/README.md](../../tests/README.md)）：

- 不访问真实模型 / Hub / 用户数据；
- 使用 `tmp_path`、fixture、fake 外部依赖；
- 只收集主程序 `tests/`，不收集插件测试；
- 标记：`integration`、`optional`。

### 6.2 前端

```bash
cd frontend-v2
npm ci
npm run typecheck
npm run lint
npm test
npm run build
```

### 6.3 E2E

```bash
cd frontend-v2
npm run test:e2e:smoke
npm run test:e2e:visual
npm run test:e2e:mobile
```

E2E 由 [scripts/run_e2e.py](../../scripts/run_e2e.py) 启动干净的临时数据环境，使用 [scripts/prepare_e2e_data.py](../../scripts/prepare_e2e_data.py) 与 fake Hub。

### 6.4 CI

[ci.yml](../../.github/workflows/ci.yml)：

| Job | 内容 |
|---|---|
| Backend | ruff、mypy、Portable lock 校验、pytest + coverage |
| Frontend | locales check、typecheck、lint、vitest、build |
| Browser smoke | Playwright Chromium 冒烟 |

其他工作流：

- `docker.yml`：镜像构建与发布；
- `release.yml`：桌面/Portable 发布与更新包。

---

## 7. 质量与架构守卫

```bash
python -m ruff check src/
python -m mypy
python -m pytest -q tests/architecture/
```

审计脚本：

| 脚本 | 用途 |
|---|---|
| `scripts/audit_architecture.py` | 架构边界审计 |
| `scripts/architecture_fitness.py` | 架构适应度函数 |
| `scripts/audit_api_contracts.py` | API 契约审计 |
| `scripts/audit_module_pluggability.py` | 模块可插拔性报告 |
| `scripts/audit_rules.py` | 规则审计 |
| `scripts/audit_text_i18n.py` | 文本 i18n 审计 |

`mypy` 只检查 [pyproject.toml](../../pyproject.toml) 中白名单文件，逐步扩展；全量 `src/` 仍有历史类型债。

---

## 8. 日志与诊断

| 项 | 位置 |
|---|---|
| 运行日志 | `data/`（`configure_runtime_logging`，默认保留天数见 `RETENTION_DAYS`） |
| 对局日志 | `data/saves/<key>/chatlog.jsonl` |
| 健康事件 | `modules.health`，通过健康面板查看 |
| Windows 原生崩溃 | WER / 启动器诊断 |
| DF Agent 日志诊断 | `src/runtime_diagnostics.py`、`src/webui/services/logs.py` |

---

## 9. 常见任务配方

### 9.1 新增一个 HTTP 功能

```text
1. src/webui/routes/<domain>.py 注册 handler（HTTP 形状 + 权限）
2. WebAPI 增加委托方法（必要时）
3. src/webui/services/<domain>.py 实现用例
4. 核心逻辑落到 engine / ruleset
5. tests/test_<domain>*.py 覆盖权限与错误
```

### 9.2 新增持久化字段

```text
1. 确认 owner（GameInstance 或 modules/<module>）
2. GamePersistedState + codec encode/decode
3. migrations/instance.py 新版本迁移
4. reset / restart / rollback 语义
5. projection（如 UI/LLM 需要）
6. tests：旧存档、未来版本、往返 codec
```

### 9.3 新增规则集

```text
1. src/rulesets/<runtime>/ 实现 RulesetRuntime
2. runtime_id / runtime_version / capabilities
3. 注册到 build_default_ruleset_registry()
4. bundle / content / locale
5. tests/rulesets/
```

### 9.4 新增插件

```text
1. 选择现有 plugin_type
2. plugin.json + config.schema.json
3. 使用 src.plugin_sdk 注册 tool/provider/bridge
4. python scripts/package_plugin.py <dir>
5. 安装到 data/plugins/ 或通过市场
```

### 9.5 新增前端页面

```text
1. frontend-v2/src/features/<feature>/
2. router/index.ts 注册
3. navigation/appNavigation.ts 加入导航
4. api/client.ts 或 feature 内封装请求
5. i18n + styles/pages/<feature>.css
6. Vitest / Playwright
```

---

## 10. 故障排查

| 现象 | 排查 |
|---|---|
| 启动提示未配置主模型 | Settings → AI Providers / Model Routing |
| 端口被占用 | 修改 `TRPG_WEB_PORT` 或 `web_port` |
| 插件连不上 API | 检查 `TRPG_API_BASE` 与实际监听地址；HTTPS 内部 API 需谨慎 |
| 存档无法加载 | 查看 `state.backup.json`、日志、schema 版本 |
| 前端 404 / 白屏 | `static-v2` 是否构建；hash 路由 deep link |
| Docker 外部不可达 | 容器端口是否 `ports` 发布 |
| Bot 无响应 | Bot token、绑定 token、NapCat 连接、可见性 |
| 中文卡片乱码 | 安装 CJK 字体（Docker 镜像已内置） |
