# 07 前端

> 目录：[frontend-v2/](../../frontend-v2/) · 入口：[main.ts](../../frontend-v2/src/main.ts) · 路由：[router/index.ts](../../frontend-v2/src/router/index.ts)

## 1. 技术栈与构建

| 项 | 值 |
|---|---|
| 框架 | Vue 3.5 + TypeScript 5.7 |
| 构建 | Vite 8 + `vue-tsc` |
| 状态 | Pinia |
| 路由 | vue-router 5（**hash history**） |
| UI | naive-ui、reka-ui、lucide-vue-next |
| 样式 | Tailwind CSS 4 + 分层 CSS |
| i18n | vue-i18n |
| 单元测试 | Vitest + `@vue/test-utils` + jsdom |
| E2E | Playwright（`scripts/run_e2e.py` 启动干净数据环境） |

构建输出：

- 默认：`../static-v2`，由后端同源提供；
- standalone：`dist/`，可部署到静态主机（需配置 CORS 与后端地址）。

Vite 配置：[vite.config.ts](../../frontend-v2/vite.config.ts)。

```bash
cd frontend-v2
npm ci
npm run dev        # 开发服务器，/api 代理到 127.0.0.1:18000
npm run build      # 类型检查 + 构建到 static-v2
npm run typecheck
npm run lint
npm test
npm run test:e2e:smoke
```

---

## 2. 目录结构

```text
frontend-v2/src/
├─ api/                 # 后端 API client 与类型
├─ components/          # 通用 UI（ActionComposer、GameTimeline、AssistantPanel…）
├─ composables/         # 可复用状态/行为（useGame、useAssistant、useTheme…）
├─ features/            # 按功能域组织的页面与子组件
│  ├─ admin/            # 角色、冒险、记忆、日志、规则、设置
│  ├─ adventures/       # 冒险工作台
│  ├─ assistant/        # DF Agent 面板
│  ├─ auth/             # 登录
│  ├─ characters/       # 角色管理
│  ├─ content-review/   # 内容审核
│  ├─ create/           # 创建对局
│  ├─ creator/          # 内容创作
│  ├─ game-preferences/ # 本局偏好
│  ├─ game-profiles/    # 剧本/存档入口
│  ├─ legal/            # 条款
│  ├─ library/          # 内容库
│  ├─ lorebook/         # 世界书
│  ├─ maps/             # 地图
│  ├─ modules/          # 模组
│  ├─ onboarding/       # 新手引导
│  ├─ overview/         # 大厅
│  ├─ peer/             # P2P 直连
│  ├─ play/             # 游玩主页面与玩法子域
│  ├─ player/           # 玩家加入
│  ├─ plugins/          # 插件管理
│  ├─ rulesets/         # 规则集 UI（含 dnd2024 战斗）
│  └─ worlds/           # 世界
├─ i18n/                # 语言资源与策略
├─ navigation/          # 顶栏/侧栏导航定义
├─ peer/                # P2P 客户端与桥接
├─ router/              # 路由与守卫
├─ stores/              # Pinia store
├─ styles/              # tokens / tailwind / shared / navigation / pages
├─ utils/               # 通用工具
├─ App.vue
└─ main.ts
```

---

## 3. 路由与页面

[router/index.ts](../../frontend-v2/src/router/index.ts)：

| 路径 | 页面 |
|---|---|
| `/login` | `features/auth/LoginView.vue` |
| `/overview` | 大厅 |
| `/create` | 创建对局 |
| `/play` | `features/game-profiles/PlayEntry.vue`（再进入具体游戏） |
| `/join` | 玩家加入 |
| `/peer` | P2P 直连 |
| `/characters` | 角色管理 |
| `/library` | 内容库 |
| `/creator` | 内容创作 |
| `/map` | 地图 |
| `/lorebook` | 世界书 |
| `/worlds` | 世界 |
| `/adventures` | 冒险 |
| `/modules` / `/modules/:moduleId` | 模组 |
| `/memory` / `/logs` / `/rules` / `/settings` | 管理 |
| `/plugins` | 插件 |
| `/legal/terms` / `/legal/privacy` | 法务 |

公开路由：

- `login`；
- `join`；
- `peer`；
- `legal-*`；
- 带 `?user=` 或 `?share=` 的 `play`。

其他路由由 `requireOwnerAccess(...)` 守卫。

---

## 4. API 客户端

[api/client.ts](../../frontend-v2/src/api/client.ts)：

- `api<T>(path, options)`：统一请求、错误映射、凭据头；
- `ApiError`：带 `status` / `code` / `retryAfter`；
- `retryOnRateLimit(...)`：仅用于幂等的“进入游戏”写入；
- `gameEventSource(gameKey, cursor)`：先换 SSE ticket，再创建 `EventSource`；
- 请求自动带上房间令牌 / 席位令牌 / owner 凭据；
- 分享链接玩家使用 seat token，而不是公开 uid。

类型定义集中在 [api/types.ts](../../frontend-v2/src/api/types.ts)（约 62KB）。

---

## 5. SSE 与状态同步

[composables/useGame.ts](../../frontend-v2/src/composables/useGame.ts)：

```text
加载游戏详情
  → 建立 SSE
  → 收到回合/状态事件
  → 更新 timeline / 角色面板 / 快捷行动 / 经济提示
  → 断线按 cursor 重连
```

要点：

- SSE 事件不会直接修改服务端状态；
- 玩家提交行动后，以服务端返回与后续 SSE 为准；
- 权限撤销会触发断开与重新登录；
- `gameSse.ts` 封装连接细节。

---

## 6. 游玩主页面（`features/play/`）

| 文件 / 目录 | 作用 |
|---|---|
| `PlayView.vue` | 主页面（约 94KB）：时间线、行动输入、侧栏、面板编排 |
| `ActionCheckOptions.vue` | 行动前的检定选项 |
| `InviteQrModal.vue` | 邀请二维码 |
| `RoomPasswordDialog.vue` | 房间密码 |
| `useActionSkill.ts` | 行动技能选择 |
| `usePlayReactions.ts` | 游玩交互反馈 |
| `economyPrompts.ts` | 经济提示文案 |
| `dice/` | 骰子展示 |
| `check-decisions/` | Push / 检定决策 |
| `check-modes/` | 检定模式 |
| `manual-rolls/` | 手动骰 |
| `party/` | 队伍状态 |
| `recovery/` | 资源恢复 |
| `rest-notices/` | 休息提示 |
| `run-story/` | 跑团计划 / 幕间 / 结团 |
| `ai-seats/` | AI 席位 |
| `preferences/` | 快捷行动显示偏好（localStorage，按游戏 + actor） |
| `story/` | 叙事片段 |
| `surface/` | 页面布局外壳 |
| `workbench/` | 工作台 |

`features/rulesets/dnd2024/combat/` 展示服务端投影的战斗状态；前端不自行结算命中/伤害。

---

## 7. 能力门控（Capability Gating）

规则：

- 使用后端返回的 `ruleset capabilities` 与 `available_intents` 决定按钮/面板是否出现；
- 不根据“名字像 D&D”或本地规则名推断能力；
- 不用按钮是否显示代替服务端权限检查；
- 服务端始终重新校验。

示例：

```text
capabilities.deterministic_combat → 显示战斗面板
capabilities.combat_scheduler    → 显示行动条 / 调度控件
available_intents                → 显示可用动作
```

---

## 8. 样式体系

[styles/README.md](../../frontend-v2/src/styles/README.md)。单一入口：

```text
styles/index.css
├─ shared.css        # 基础与控件
├─ navigation.css    # 应用与二级导航
└─ pages/<feature>.css  # 页面布局、状态与媒体查询
```

其他边界：

- `tokens.css`：设计 token；
- `tailwind.css`：Tailwind 层；
- `markdown.css`：Markdown 渲染；
- `theme.ts`：主题切换；
- 组件内样式由所属 feature 维护。

不要再新增“同页覆盖补丁层”；修改页面时直接编辑所属样式文件。

---

## 9. i18n

[i18n/](../../frontend-v2/src/i18n/)：

- 核心 UI 支持英文与简体中文；
- 社区翻译（日语、德语、俄语等）缺失时回退英文；
- `locales:check` 校验核心翻译与回退；
- Locale 不得改变 mechanics；
- 后端也维护语言策略（`src/engine/language.py`、`src/localization/`）。

---

## 10. Frontend 边界规则

| 规则 | 原因 |
|---|---|
| 不复制后端 Content V2 逻辑 | 避免两套身份/locale 规则 |
| 不自行计算 HP / 伤害 / 余额 | 服务端才是权威 |
| 不把按钮显示当权限 | 服务端必须再次校验 |
| 不直接依赖插件内部实现 | 只通过 API / capability |
| deep link 先等 `router.isReady()` | 避免 401 与错误守卫 |
| 构建后 chunk 失效要恢复 | `installRuntimeRecovery(router)` |

---

## 11. 关键文件速查

| 文件 | 说明 |
|---|---|
| [main.ts](../../frontend-v2/src/main.ts) | 应用挂载、视口变量、运行时恢复 |
| [App.vue](../../frontend-v2/src/App.vue) | 根组件与布局 |
| [router/index.ts](../../frontend-v2/src/router/index.ts) | 路由与 owner 守卫 |
| [api/client.ts](../../frontend-v2/src/api/client.ts) | API / SSE / 错误 |
| [api/types.ts](../../frontend-v2/src/api/types.ts) | 后端 JSON 类型 |
| [composables/useGame.ts](../../frontend-v2/src/composables/useGame.ts) | 对局状态与 SSE |
| [components/ActionComposer.vue](../../frontend-v2/src/components/ActionComposer.vue) | 行动输入 |
| [components/GameTimeline.vue](../../frontend-v2/src/components/GameTimeline.vue) | 时间线 |
| [features/play/PlayView.vue](../../frontend-v2/src/features/play/PlayView.vue) | 游玩主页 |
| [features/create/CreateView.vue](../../frontend-v2/src/features/create/CreateView.vue) | 创建对局 |
| [navigation/appNavigation.ts](../../frontend-v2/src/navigation/appNavigation.ts) | 导航定义 |
| [styles/README.md](../../frontend-v2/src/styles/README.md) | 样式组织规则 |

---

## 12. 前端改动检查清单

- [ ] 新页面是否加入 router 与导航？
- [ ] 是否从后端 capability / available_intents 派生显示？
- [ ] 是否有服务端权限校验对应？
- [ ] 是否处理 401 / 403 / 404 / 409 / 429？
- [ ] 是否补充 Vitest 测试？
- [ ] 是否需要更新 E2E 冒烟用例？
- [ ] 样式是否写入所属 `pages/<feature>.css`，而不是追加覆盖层？
- [ ] 文本是否同时补中英文？
