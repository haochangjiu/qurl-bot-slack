# Nginx 自签证书 + 反代 qurl-bot-slack（测试用）

场景示例：

- 对外：`https://36.148.24.208:14012/slack/install`、`.../slack/oauth_redirect`
- 本机应用：`http://127.0.0.1:3000`（`.env` 中 `HTTP_PORT=3000`）

请将文中的 **`36.148.24.208`**、**`14012`**、**`3000`** 换成你的实际值。

---

## 1. 生成自签证书（测试用）

### 1.1 目录与权限

**若 Nginx 为系统包安装（常见 `/etc/nginx`）：**

```bash
sudo mkdir -p /etc/nginx/ssl
cd /etc/nginx/ssl
```

**若 Nginx 为源码安装到 `/usr/local/nginx`：**

```bash
sudo mkdir -p /usr/local/nginx/conf/ssl
cd /usr/local/nginx/conf/ssl
```

下文用 **`/etc/nginx/ssl`** 举例；若用源码路径，把下面所有路径改成你的 `ssl` 目录。

### 1.2 使用 OpenSSL 配置 SAN（含 IP，适配浏览器与部分客户端）

创建临时配置文件 **`/etc/nginx/ssl/openssl-san.cnf`**：

```ini
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
CN = 36.148.24.208

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment

[alt_names]
IP.1 = 36.148.24.208
```

生成 **私钥 + 证书**（有效期约 10 年）：

```bash
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/qurl-bot.key \
  -out /etc/nginx/ssl/qurl-bot.crt \
  -config /etc/nginx/ssl/openssl-san.cnf \
  -extensions v3_req
sudo chmod 640 /etc/nginx/ssl/qurl-bot.key
sudo chown root:root /etc/nginx/ssl/qurl-bot.key /etc/nginx/ssl/qurl-bot.crt
```

**说明：** 自签证书浏览器会提示「不安全」，Slack 后台是否接受因环境而异；生产请换正式域名 + Let’s Encrypt 等。

---

## 2. Nginx 站点配置

### 2.1 包安装（Debian/Ubuntu）

新建 **`/etc/nginx/sites-available/qurl-bot-slack.conf`**（或放入 `conf.d`）：

```nginx
server {
    listen 14012 ssl;
    server_name 36.148.24.208;

    ssl_certificate     /etc/nginx/ssl/qurl-bot.crt;
    ssl_certificate_key /etc/nginx/ssl/qurl-bot.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host  $host;
        proxy_set_header X-Forwarded-Port  $server_port;

        proxy_read_timeout 60s;
    }
}
```

启用站点（若使用 `sites-enabled`）：

```bash
sudo ln -sf /etc/nginx/sites-available/qurl-bot-slack.conf /etc/nginx/sites-enabled/
```

确保主配置 **`http { ... }`** 里有 `include /etc/nginx/sites-enabled/*;`（或把 `server` 块直接写进 `nginx.conf`）。

### 2.2 包安装（CentOS / RHEL，常用 `conf.d`）

新建 **`/etc/nginx/conf.d/qurl-bot-slack.conf`**，内容与上一节 **`server { ... }`** 相同（证书路径仍指向 `/etc/nginx/ssl/`）。

### 2.3 源码安装（prefix `/usr/local/nginx`）

把证书放在 **`/usr/local/nginx/conf/ssl/`**，在 **`/usr/local/nginx/conf/nginx.conf`** 的 `http` 块内 **`include`** 一个子文件，或直接把 `server` 写进去，例如：

```nginx
ssl_certificate     /usr/local/nginx/conf/ssl/qurl-bot.crt;
ssl_certificate_key /usr/local/nginx/conf/ssl/qurl-bot.key;
```

其余 `location` 与上文一致。

---

## 3. 应用 `.env`（与 Slack 一致）

```env
HTTP_HOST=0.0.0.0
HTTP_PORT=3000
SLACK_REDIRECT_URI=https://36.148.24.208:14012/slack/oauth_redirect
```

Slack 后台 **Redirect URLs** 与 **`SLACK_REDIRECT_URI`** 必须**完全一致**。

---

## 4. 检查、启动、重载

### 4.1 系统包安装的 `nginx`（在 PATH 中）

```bash
sudo nginx -t
sudo systemctl start nginx      # 首次
sudo systemctl enable nginx     # 开机自启（可选）
sudo systemctl reload nginx     # 改配置后
```

查看状态：

```bash
sudo systemctl status nginx
```

### 4.2 源码安装到 `/usr/local/nginx`

```bash
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx              # 启动（若未用 systemd）
sudo /usr/local/nginx/sbin/nginx -s reload    # 重载
sudo /usr/local/nginx/sbin/nginx -s stop     # 停止
```

若已按前文配置 **systemd** `nginx.service`，则同样可用：

```bash
sudo systemctl start nginx
sudo systemctl reload nginx
```

---

## 5. 防火墙与安全组

- 放行 **TCP 14012**（公网访问 HTTPS）。
- **不要**把 **3000** 暴露到公网；应用只监听本机或内网即可。

---

## 6. 本机自检

```bash
curl -skI https://127.0.0.1:14012/slack/install
curl -sI http://127.0.0.1:3000/slack/install
```

`-k` 表示不信任自签证书，仅用于本机测试。

---

*证书与端口可按实际环境修改；生产环境请使用可信 CA 签发的证书。*
