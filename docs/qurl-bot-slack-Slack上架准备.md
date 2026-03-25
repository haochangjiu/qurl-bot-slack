# qurl-bot-slack：Slack 应用上架准备指南（中文）

本文面向将 **qurl-bot-slack** 提交至 **Slack 应用目录（App Directory）** 或开启 **公开分发（Manage distribution）** 前的准备与测试。请先完成文中 **「上架前测试清单」** 全部项，再进入正式上架流程。

---

## 1. 文档用途与推荐顺序

| 阶段 | 说明 |
|------|------|
| **阶段 0** | 在 [api.slack.com/apps](https://api.slack.com/apps) **创建应用并完成后台配置**（本文 **第 2 节**），取得凭证并写入 `.env`。 |
| **阶段 A** | 在测试环境完成 **「上架前测试清单」**（本文 **第 5 节**，**必须先做**）。 |
| **阶段 B** | 准备程序以外的材料与合规页面（**第 4 节**）。 |
| **阶段 C** | 对照注意事项、官方清单并提交上架（**第 3、6、7 节**）。 |

Slack 官方应用审查清单（英文）：[Slack App Directory checklist](https://api.slack.com/docs/slack-apps-checklist) —— 上架前请逐条对照。

---

## 2. Slack 应用注册与后台配置（api.slack.com/apps）

本节描述从 **零创建 Slack 应用** 到与 **qurl-bot-slack** 对齐的完整过程。后台界面可能随 Slack 更新略有差异，以控制台实际文案为准。

### 2.1 创建应用

1. 使用浏览器打开 **[https://api.slack.com/apps](https://api.slack.com/apps)** 并登录你的 Slack 账号。
2. 点击 **Create New App**。
3. 选择 **From scratch**（从头创建）。  
   - 若团队已有 **App manifest**（YAML），可选用 **From an app manifest**，需自行保证与本文 scope、事件一致。
4. 填写：
   - **App Name**：例如 `qurl-bot-slack`（上架前可再优化展示名）。
   - **Pick a workspace to develop your app in**：选择用于开发的 **测试工作区**（Development workspace）。
5. 创建完成后进入该应用的配置页，左侧为各功能菜单。

### 2.2 Basic Information（基础信息）

1. 打开 **Settings → Basic Information**。
2. 在 **App Credentials** 中记录（填入服务器 `.env`，**勿提交到 Git**）：
   - **Client ID** → `SLACK_CLIENT_ID`
   - **Client Secret** → `SLACK_CLIENT_SECRET`
   - **Signing Secret** → `SLACK_SIGNING_SECRET`
3. **Display Information**（展示信息）：上架前建议补全 **App icon**、**Short description** 等；App Directory 对图片尺寸与文案有要求，以 Slack 提示为准。
4. **Install your app**（安装到开发工作区）：完成下文 OAuth 与权限配置后，可在此页或 **Install to Workspace** 先做一次开发环境安装验证。

### 2.3 Socket Mode（必开）

1. 打开 **Settings → Socket Mode**。
2. **Enable Socket Mode** 设为开启。
3. 创建 **App-Level Token**：
   - 点击 **Generate**，输入 token 名称（任意，如 `socket`）。
   - 勾选 scope：**connections:write**。
4. 生成后复制 **Token**（以 `xapp-` 开头）→ 填入 `.env` 的 **`SLACK_APP_TOKEN`**。

### 2.4 OAuth & Permissions（OAuth 与权限）

1. 打开 **Features → OAuth & Permissions**。
2. **Redirect URLs**（重定向地址）：  
   - 点击 **Add New Redirect URL**，添加与运行环境 **完全一致** 的回调地址，例如：  
     - 生产：`https://你的域名/slack/oauth_redirect`  
     - 本地开发（需在 Slack 后台同样添加）：`http://127.0.0.1:8080/slack/oauth_redirect`（端口与 `HTTP_PORT` 一致）  
   - 保存后，将最终使用的这一条写入 `.env` 的 **`SLACK_REDIRECT_URI`**（**字符级一致**，含 `http`/`https`、路径、末尾斜杠）。
3. **Scopes → Bot Token Scopes** 中依次添加（与 `config.py` / `README` 默认一致）：

   | Scope |
   |-------|
   | `app_mentions:read` |
   | `chat:write` |
   | `im:history` |
   | `im:read` |
   | `im:write` |
   | `users:read` |
   | `commands` |

4. **User Token Scopes**：本仓库默认 **不需要** 为普通功能添加；仅当你启用 **Admin API 兜底**（`USE_ADMIN_ROLES_API_FALLBACK` + `SLACK_ADMIN_USER_TOKEN`）时，在 Slack 侧需单独走用户 OAuth，不在此展开。
5. 修改 scope 后，通常需要在 **Install to Workspace** 处 **重新授权** 开发工作区，以免 token 权限不足。

### 2.5 Event Subscriptions（事件订阅）

1. 打开 **Features → Event Subscriptions**。
2. **Enable Events** 打开。
3. 在 **Subscribe to bot events** 中添加：

   | Event |
   |-------|
   | `app_home_opened` |
   | `app_mention` |
   | `message.im` |

4. 使用 **Socket Mode** 时，一般 **不需要** 配置 **Request URL** 来接收事件（由 Socket 连接推送）。若界面仍显示 Request URL，可留空或按 Slack 当前说明处理。

### 2.6 Slash Commands（斜杠命令）

1. 打开 **Features → Slash Commands**。
2. 依次 **Create New Command** 创建（名称与代码一致，上架时可加应用前缀以防冲突）：
   - `/setkey`
   - `/mykey`
   - `/delkey`
3. **Request URL**：创建命令时若 **必须** 填写，请填：  
   `https://你的公网域名/slack/events`  
   （与程序内 `bolt_app.server(..., path="/slack/events")` 一致；本地开发可用 `https://xxx.ngrok.io/slack/events` 等 **HTTPS** 隧道地址。）  
   使用 Socket Mode 时，命令投递常通过 Socket 完成；若 Slack 仍校验 URL，需保证该 HTTPS 地址可从公网访问到本进程。
4. **Short description**、**Usage hint** 建议填写，便于审核与用户理解。

### 2.7 App Home（若使用欢迎页）

1. 打开 **Features → App Home**。
2. 按需开启 **Show Tabs → Messages Tab** / **Home Tab**（与你的产品体验一致即可）。  
3. 本仓库在 `app_home_opened` 时发布欢迎内容，需已订阅该事件（见 2.5 节）。

### 2.8 与 `.env` 的对应关系（核对用）

| Slack 后台 / 行为 | 环境变量或说明 |
|-------------------|----------------|
| Client ID / Secret / Signing Secret | `SLACK_CLIENT_ID`、`SLACK_CLIENT_SECRET`、`SLACK_SIGNING_SECRET` |
| App-Level Token（`xapp-`） | `SLACK_APP_TOKEN` |
| Redirect URL 之一 | `SLACK_REDIRECT_URI`（与之一致） |
| 安装后浏览器访问安装链接 | `https://你的域名/slack/install`（程序内 `oauth_install_path` 默认为 `/slack/install`） |

完成以上配置后，在服务器配置 `ANTHROPIC_API_KEY`、`LAYERV_*` 等（见 `.env.example`），启动 `python app.py`，再在浏览器用安装链接测试 OAuth（详见 **第 5 节** 测试清单）。

### 2.9 公开分发与 App Directory（上架入口）

1. 打开 **Settings → Manage distribution**（或 **Distribute App**）。
2. 按 Slack 向导完成 **公开分发** 前置条件（隐私政策、支持联系方式等，与 **第 4 节** 一致）。
3. 若需出现在 **Slack Marketplace / App Directory**，在控制台中按流程提交 **列表信息、截图** 等；具体要求以当时 Slack 界面为准。

---

## 3. 上架注意事项（与本项目相关）

### 3.1 技术架构要点

- **OAuth 多工作区安装**：用户通过浏览器访问 `https://你的域名/slack/install` 安装；回调地址必须与 `.env` 中 `SLACK_REDIRECT_URI` **完全一致**，且生产环境 **HTTPS**。
- **Socket Mode**：事件通过 Socket Mode 接收，**不要求** 将 Events 请求 URL 暴露到公网（但 OAuth 的 HTTP 服务仍需公网 HTTPS 反代）。
- **数据**：默认使用本地 **SQLite**（`SQLITE_DATABASE_PATH`）存储安装信息与 bot token；需评估备份、磁盘与多实例部署（多实例时 SQLite 不适用，需改为共享存储或单实例）。

### 3.2 权限与最小 scope

默认 Bot Token Scopes（与 `config.py` / README 一致）：

`app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`, `commands`

- **仅申请业务必需权限**；若上架说明中写的功能与 scope 不一致，容易被拒。
- 若未来增加 scope，**必须**同步更新 Slack 应用配置、用户文档与隐私说明。

### 3.3 斜杠命令与命名

- README 建议为 Marketplace 命令加 **应用名前缀** 以降低冲突；上架前请固定命令名并在 **Slash Commands** 中配置。
- 本仓库中的 Key 相关命令：`/setkey`、`/mykey`、`/delkey`（**仅在私信 DM 中可用**，频道内禁止，防泄露）。

### 3.4 LayerV / Anthropic（合规与披露）

- 使用 **LayerV QURL API** 与 **Anthropic（Claude）** 做意图与 URL 理解时，Slack 通常要求你在 **应用商店列表页 / 隐私政策** 中说明：
  - 是否使用 **LLM**、**哪些数据** 会发送给第三方；
  - 数据 **保留策略**；用户如何联系你删除数据。
- 请按官方 checklist 与法务要求撰写，**不要仅复制本仓库一句话**。

### 3.5 Enterprise Grid 与 Key 管理

- **Enterprise Grid**：配置 LayerV Key 的权限以 **Enterprise 组织级** Owner/Admin 为准（见代码与 `.env.example`）。
- 非 Grid 工作区可配置是否允许 **仅工作区** 管理员配置 Key；上架文档中应如实描述，避免用户误解。

---

## 4. 除程序外你需要准备的事项

以下为「代码 + `.env` 能跑」之外，上架与长期运营通常仍需要的准备。

### 4.1 基础设施与域名

| 项目 | 说明 |
|------|------|
| **公网 HTTPS** | 反向代理（Nginx、Caddy、云 LB 等）将 `https://你的域名` 指向本服务 `HTTP_HOST`/`HTTP_PORT`。 |
| **固定域名** | Redirect URL、安装链接、隐私政策 URL 均依赖稳定域名；避免使用临时隧道域名作为正式上架地址。 |
| **TLS 证书** | 有效 HTTPS 证书；Slack OAuth 回调对证书错误非常敏感。 |

### 4.2 Slack 开发者后台（非代码）

应用 **从零创建、逐步点击菜单的配置过程** 见 **第 2 节**；本节从「上架前材料核对」角度列出要点。

- **Basic Information**：应用名称、简短描述、图标、背景图（App Directory 有规格要求）。
- **OAuth & Permissions**：Redirect URLs、Bot Token Scopes 与生产一致。
- **Socket Mode**：开启并配置 App-Level Token（`connections:write`）。
- **Event Subscriptions**：订阅 `app_home_opened`、`app_mention`、`message.im` 等（与 README 一致）。
- **Slash Commands**：注册并指向你的生产环境（若 Slack 要求 Request URL，按当前实现填写）。
- **Manage distribution**：启用公开分发前完成 Slack 引导的检查项。

### 4.3 合规与对外页面（Slack 常要求）

- **隐私政策（Privacy Policy）** URL：可访问、可更新。
- **服务条款**（若适用）：部分团队会一并提供。
- **支持渠道**：支持邮箱、工单或帮助页；Slack 审核可能查看。
- **产品主页 / 落地页**（可选但利于审核）：说明功能、适用场景、与 Slack 的集成方式。

### 4.4 第三方账号与密钥

| 服务 | 用途 |
|------|------|
| **LayerV** | API Key；工作区可通过 `/setkey` 配置，或服务器 `LAYERV_API_KEY` 兜底。 |
| **Anthropic** | `ANTHROPIC_API_KEY`，用于消息理解。 |
| **运维** | 生产 `ENCRYPTION_SECRET`、密钥轮换、日志与告警策略。 |

### 4.5 品牌与文档

- 应用简介、截图、演示视频（若提交）与 **中文/英文** 说明一致。
- 若面向国际用户，建议至少提供 **英文** 商店描述与隐私政策。

---

## 5. 上架前测试清单（必须先完成）

> **说明**：以下测试应在 **独立测试工作区** 或 **预发环境** 完成，通过后再进行「正式上架 / 全量公开分发」。  
> 建议将每条结果记录为：日期、测试人、通过/失败、备注。

### 5.1 安装与 OAuth（阻断项）

- [ ] 使用 **未安装过该应用** 的测试工作区，通过 `https://你的测试域名/slack/install` 完成安装，无报错。
- [ ] 浏览器完成 OAuth 后，工作区内应用已出现且 **Bot 在线**（Socket Mode 连接成功）。
- [ ] `SLACK_REDIRECT_URI` 与 Slack 后台 **Redirect URLs** 字符级一致（含末尾 `/`、http/https）。
- [ ] 故意使用错误 Redirect URL 时，安装失败行为符合预期（无 token 泄露）。

### 5.2 Socket Mode 与事件（阻断项）

- [ ] 进程重启后，Socket Mode **自动重连**，频道与 DM 能收到事件。
- [ ] 订阅的事件（如 `app_mention`、`message.im`、`app_home_opened`）均能触发，无持续报错日志。

### 5.3 核心业务：QURL 与消息（阻断项）

- [ ] **频道 @提及**：发送 URL，机器人行为符合设计（例如 DM 投递代理链接等）。
- [ ] **私信 DM**：自然语言 + URL，能生成 QURL（需有效 LayerV Key 路径）。
- [ ] **过期时间**：如用户指定 `7d` 等，与 LayerV 返回一致或符合预期。
- [ ] **无效 URL / API 错误**：用户可见提示友好，日志无敏感信息泄露。

### 5.4 LLM（Anthropic）路径（阻断项）

- [ ] 正常消息能调用并成功解析意图（在可接受延迟内）。
- [ ] API Key 无效、限流、超时等情况下，**不崩溃**，且有明确用户提示。

### 5.5 LayerV Key 与权限（强烈建议）

- [ ] **DM 中** `/setkey`、`/mykey`、`/delkey`：工作区 **管理员** 与 **非管理员** 行为与文档一致。
- [ ] **频道中** 执行 Key 相关命令：应被拒绝或提示仅在 DM 操作（防泄露）。
- [ ] 若有 **Enterprise 测试工作区**：验证组织管理员与工作区管理员的区别是否符合你的配置。

### 5.6 App Home（若启用）

- [ ] 打开 App Home 无 500；欢迎文案正常（含中英文若均启用）。

### 5.7 安全与运维（阻断项）

- [ ] `.env`、数据库、日志中 **不出现** `SLACK_CLIENT_SECRET`、`SLACK_APP_TOKEN`、`xoxb-` 等明文。
- [ ] 生产使用强随机 `ENCRYPTION_SECRET`（勿用仓库默认值）。
- [ ] SQLite 与 `oauth_state` 目录 **权限** 合理，备份策略已记录。

### 5.8 上架材料与体验（提交前）

- [ ] 隐私政策与支持链接在浏览器中 **可打开**。
- [ ] App Directory 上的描述、截图与实际功能 **一致**。
- [ ] 已阅读 [Slack App Directory checklist](https://api.slack.com/docs/slack-apps-checklist)，并勾选可自查项。

---

## 6. 正式上架操作建议流程

1. 确认第 5 节 **全部通过** 并留档。  
2. 将生产环境指向 **正式域名与 HTTPS**，并完成第 4 节材料。  
3. 在 **Manage distribution** 中按 Slack 向导提交；若需 **App Directory 列表**，按控制台要求提交截图与说明。  
4. 审核期间保持 **支持邮箱** 可收信，及时回复 Slack 问题。  
5. 上架后监控：安装量、错误率、Socket 断线、LayerV/Anthropic 配额。

---

## 7. 常见风险与提示

- **Scope 过多**：易被拒；保持与 README 默认一致，除非确有功能需要。  
- **隐私政策空洞**：未说明 LLM 与第三方 API 时，审核风险高。  
- **测试不充分**：OAuth 仅本地测过、生产域名未测，易导致上架后大规模安装失败。  
- **单点 SQLite**：计划多实例前需先解决存储与安装数据一致性。

---

*文档版本与仓库 `qurl-bot-slack` 实现对应；若 Slack 政策或本仓库配置变更，请同步更新本文与 `README.md`。*
