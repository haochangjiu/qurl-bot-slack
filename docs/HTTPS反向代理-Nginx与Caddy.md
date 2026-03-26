# 使用 Nginx / Caddy 为 qurl-bot-slack 提供 HTTPS（完整步骤）

假设：

- 你已有一台 **公网 Linux 服务器**（示例以 **Ubuntu 22.04 / Debian 12** 为例，命令略有差异时用包管理器等价替换即可）。
- 有一个 **域名**（下文用 `bot.example.com`），DNS **A 记录** 已指向该服务器公网 IP。
- 本仓库进程在 **本机 HTTP** 监听（默认 `127.0.0.1:8080`，由 `HTTP_HOST`/`HTTP_PORT` 控制）；**不在 Python 里直接开 HTTPS**，由反向代理终止 TLS。

---

## 第 0 步：准备与检查

### 0.1 防火墙与安全组

- 云厂商安全组 / 本机 `ufw`：**放行 TCP 80、443**（Let’s Encrypt HTTP-01 验证需要 **80**；若你改用 DNS 验证，可只开 443，本文不展开）。
- **不要**把 `8080` 暴露到公网（应用只监听 `127.0.0.1` 或 `0.0.0.0` 仅本机访问时，确保外网只打到 80/443）。

### 0.2 应用已能本机访问

```bash
curl -sI http://127.0.0.1:8080/slack/install
```

应返回 HTTP 头（非连接失败）。端口以 `.env` 中 `HTTP_PORT` 为准。

### 0.3 后续要改的配置（两处必须一致）

- `.env`：`SLACK_REDIRECT_URI=https://bot.example.com/slack/oauth_redirect`（域名换成你的）。
- Slack 开发者后台：**OAuth & Permissions → Redirect URLs** 添加上述 **同一 URL**。

安装链接（给用户）：`https://bot.example.com/slack/install`。

---

## 方案 A：Caddy（自动 HTTPS，配置最少）

### A.1 安装 Caddy

```bash
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

（若官方安装说明有更新，以 [Caddy 安装文档](https://caddyserver.com/docs/install) 为准。）

### A.2 写入站点配置

编辑 `/etc/caddy/Caddyfile`（或按发行版在 `Caddyfile` 中 `import` 子文件），示例：

```caddy
bot.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

将 `bot.example.com` 换成你的域名；`8080` 与 `HTTP_PORT` 一致。

### A.3 启动并开机自启

```bash
sudo systemctl enable --now caddy
sudo systemctl status caddy
```

Caddy 会自动申请并续期 Let’s Encrypt 证书（需 **80/443 可达** 且域名解析正确）。

### A.4 验证 HTTPS

```bash
curl -sI https://bot.example.com/slack/install
```

浏览器应显示锁标；若证书错误，检查 DNS 与防火墙。

---

## 方案 B：Nginx + Certbot（Let’s Encrypt，常见组合）

### B.1 安装 Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### B.2 先配置 HTTP 反代（再签发证书）

创建 `/etc/nginx/sites-available/qurl-bot-slack`：

```nginx
server {
    listen 80;
    server_name bot.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用站点并测试：

```bash
sudo ln -sf /etc/nginx/sites-available/qurl-bot-slack /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

将 `bot.example.com` 与 `8080` 换成你的值。

### B.3 安装 Certbot 并签发证书

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d bot.example.com
```

按提示输入邮箱、同意条款；Certbot 会修改 Nginx 为 **443 + SSL**，并配置续期。

### B.4 验证续期

```bash
sudo certbot renew --dry-run
```

### B.5 验证 HTTPS

```bash
curl -sI https://bot.example.com/slack/install
```

---

## 应用与 Slack 最终核对

1. **qurl-bot-slack** 进程运行中（如 `python app.py` 或 `systemctl` + `deploy.sh` 部署的 unit）。
2. `.env` 中 `SLACK_REDIRECT_URI` 为 **`https://你的域名/slack/oauth_redirect`**（无多余斜杠、与 Slack 后台一致）。
3. Slack：**Redirect URLs** 与上一条 **完全一致**。
4. 若 Slash Command 要求 Request URL：使用 `https://你的域名/slack/events`（与代码中 `path="/slack/events"` 一致）。

---

## 可选：仅本机监听，避免误暴露 8080

若希望 Python 只监听回环地址，在 `.env` 中设置：

```env
HTTP_HOST=127.0.0.1
HTTP_PORT=8080
```

则只有 Nginx/Caddy 能连到应用，公网只能通过 443 访问。

---

## 常见问题

| 现象 | 排查 |
|------|------|
| **502 Bad Gateway** | 应用未启动；或 `proxy_pass` 端口与 `HTTP_PORT` 不一致；或 `HTTP_HOST` 未监听在 127.0.0.1。 |
| **证书申请失败** | DNS 未解析到本机；80 被占用或未放行；域名拼写错误。 |
| **Slack OAuth 重定向失败** | `SLACK_REDIRECT_URI` 与 Slack 后台不一致；或 `scheme`/`host`/`path` 拼写错误。 |

---

*文档仅作运维参考；发行版与 Caddy/Nginx 版本差异以官方文档为准。*
