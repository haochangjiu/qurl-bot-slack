# CentOS 7 服务器：修复 yum（python-pycurl）与安装 Git（可执行步骤）

适用于：**`yum` 报 `No module named pycurl`**、**`curl` 异常**，或需 **Git 2.x** 的场景。  
以下命令在服务器 **SSH 登录后** 逐段执行；**`<ARCH>`** 一般为 `x86_64`（`uname -m` 查看）。

---

## 第 1 步：确认环境

```bash
uname -m
cat /etc/redhat-release
which python2
/usr/bin/python2 --version
```

---

## 第 2 步：下载 `python-pycurl` RPM（Vault 镜像，避免 404）

CentOS 7 已 EOL，请使用 **vault** 路径。任选 **一个** 能访问的镜像。

### 2.1 设置变量（便于改镜像）

```bash
cd /tmp
ARCH=$(uname -m)
# 国内常用（阿里云 vault）
VAULT_BASE="https://mirrors.aliyun.com/centos-vault/7.9.2009/os/${ARCH}/Packages"
# 备用：官方 vault
# VAULT_BASE="https://vault.centos.org/7.9.2009/os/${ARCH}/Packages"
```

### 2.2 下载（优先 `wget`，没有再用 `curl`）

包名在 7.9.2009 中一般为下列之一，**若 404 请到目录页核对文件名**（见 2.4）。

```bash
# 常见文件名（与 7.9.2009 一致；若失败见 2.4）
RPM="python-pycurl-7.19.0-19.el7.${ARCH}.rpm"

if command -v wget >/dev/null 2>&1; then
  wget "${VAULT_BASE}/${RPM}" -O "${RPM}"
else
  # 若 curl 报 libcurl 错误，可加 -q 忽略 ~/.curlrc
  curl -q -fL "${VAULT_BASE}/${RPM}" -o "${RPM}"
fi

ls -la "${RPM}"
```

### 2.3 安装

```bash
sudo rpm -Uvh --replacepkgs "${RPM}"
```

### 2.4 若提示 404：手动查准确文件名

用浏览器打开（把 `x86_64` 换成你的架构）：

- `https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/`

页面中搜索 **`python-pycurl`**，复制 **完整 `.rpm` 文件名**，再执行：

```bash
cd /tmp
RPM='这里粘贴完整文件名'
wget "${VAULT_BASE}/${RPM}" -O "${RPM}"
sudo rpm -Uvh --replacepkgs "${RPM}"
```

---

## 第 3 步：验证 `pycurl` 与 `yum`

```bash
/usr/bin/python2 -c "import pycurl; print('pycurl ok')"
sudo /usr/bin/python2 /usr/bin/yum --version
```

若仍报错，再装齐常用 Python2 相关包（需 `yum` 已可用）：

```bash
sudo /usr/bin/python2 /usr/bin/yum install -y python python-libs python-urlgrabber rpm-python
```

---

## 第 4 步：修复 `curl`（若之前有 `unknown option` / libcurl 异常）

```bash
sudo /usr/bin/python2 /usr/bin/yum reinstall -y curl libcurl
curl -V
```

可选：检查是否有不兼容的 `~/.curlrc`：

```bash
[ -f ~/.curlrc ] && head -20 ~/.curlrc
# 若有可疑项，可临时：mv ~/.curlrc ~/.curlrc.bak
```

---

## 第 5 步：安装 / 重装 Git（官方源，版本仍为 1.8.x）

不增加第三方仓库时：

```bash
sudo /usr/bin/python2 /usr/bin/yum remove -y git 2>/dev/null || true
sudo /usr/bin/python2 /usr/bin/yum install -y git
git --version
```

---

## 第 6 步（可选）：安装 Git 2.x（需增加 IUS 源）

若 **`git clone https://github.com/...` 仍因 TLS/老 Git 失败**，可启用 IUS：

```bash
sudo /usr/bin/python2 /usr/bin/yum install -y epel-release
sudo /usr/bin/python2 /usr/bin/yum install -y https://repo.ius.io/ius-release-el7.rpm
sudo /usr/bin/python2 /usr/bin/yum install -y git236
sudo yum install -y git236   # 若默认 yum 已恢复也可
git --version
```

若包名不是 `git236`，先搜索：

```bash
yum search git2 | head -40
```

---

## 第 7 步：克隆本仓库（示例）

```bash
cd /opt
sudo git clone https://github.com/haochangjiu/qurl-bot-slack.git
```

若 HTTPS 仍失败，可用 **SSH**（需先在 GitHub 添加 SSH 公钥）：

```bash
git clone git@github.com:haochangjiu/qurl-bot-slack.git
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `yum` 仍报 `pycurl` | 确认 `rpm -q python-pycurl` 已安装；`rpm -V python-pycurl` 是否通过 |
| `sudo: yum: command not found` | 使用全路径：`/usr/bin/python2 /usr/bin/yum` |
| Vault 下载慢 | 换 `mirrors.tuna.tsinghua.edu.cn/centos-vault` 同路径 |
| 坚持不加 IUS | 只能用源码或二进制安装 Git 2.x（本文未展开） |

---

*执行环境与镜像可能变化；若某 URL 失效，请以 vault 目录页中的真实文件名为准。*
