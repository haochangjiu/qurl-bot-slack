# CentOS 7 服务器：yum / 源 / Python / sqlite / git 完整修复与部署

适用于：**ECS 上 CentOS 7（或兼容 EL7）** 出现下列任一情况：

- `sudo yum` 报 **Python 3 的 SyntaxError**（`except KeyboardInterrupt, e:`）
- `/etc/yum.repos.d/*.repo` **解析错误**（如 `ority`、行断裂）
- `python-pycurl` / **`CRYPTO_num_locks`**
- **`ModuleNotFoundError: No module named '_sqlite3'`**（自编译 `/usr/local` Python）
- **`git clone` HTTP/2 报错**（`curl 16 Error in the HTTP2 framing layer`）

**说明：** 若系统为 **Alibaba Cloud Linux** 或其它衍生版，部分包名/源与纯 CentOS 7 略有差异，请以 `cat /etc/os-release` 为准；下文以 **CentOS 7 + vault** 为主。

---

## 一、先确认环境（必做）

```bash
cat /etc/os-release
uname -m
which python python2 python3 2>/dev/null
ls -la /usr/bin/python /usr/bin/python2 /usr/bin/python3 2>/dev/null
head -1 /usr/bin/yum
```

记下：架构（多为 `x86_64`）、`/usr/bin/python` 是否指向 **python3**。

---

## 二、让 `yum` 用 Python 2（修复 SyntaxError）

**原因：** CentOS 7 的 `/usr/bin/yum` 依赖 **Python 2**；若 `/usr/bin/python` 被改成 **Python 3**，会出现 `SyntaxError: multiple exception types must be parenthesized`。

**做法 A（推荐）：用 alternatives 切回 2.x（若已配置）**

```bash
sudo alternatives --config python
# 选择 python2.7 或带 2 的项
```

**做法 B：手动把默认 `python` 指回 2.7**

```bash
test -x /usr/bin/python2.7 && sudo ln -sf /usr/bin/python2.7 /usr/bin/python
```

**验证：**

```bash
/usr/bin/python --version   # 应显示 2.7.x
sudo yum --version
```

若仍用 `python2` 显式调用：

```bash
sudo /usr/bin/python2 /usr/bin/yum --version
```

---

## 三、修复 `/etc/yum.repos.d` 解析错误（含 `ority` / 行断裂）

**原因：** `.repo` 文件被改坏、截断，或 **CentOS 7 官方源已下线**，需改用 **vault**。

**1）备份并查看出错行**

```bash
sudo cp -a /etc/yum.repos.d/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo.bak.$(date +%s)
sudo nl -ba /etc/yum.repos.d/CentOS-Base.repo | sed -n '1,80p'
```

删除或合并 **残缺行**（如单独一行的 `ority`），保证每个 `[xxx]` 段内只有合法键：`name=`、`baseurl=` 或 `mirrorlist=`、`enabled=`、`gpgcheck=` 等。

**2）整文件替换为 vault（CentOS 7.9，国内可用阿里云 vault）**

先备份整个目录：

```bash
sudo mkdir -p /root/yum.repos.d.bak
sudo cp -a /etc/yum.repos.d/*.repo /root/yum.repos.d.bak/ 2>/dev/null || true
```

将 **`/etc/yum.repos.d/CentOS-Base.repo`** 内容替换为下面之一（**二选一**）。

**方案 A：阿里云 CentOS Vault（国内常用）**

```ini
# CentOS-Base.repo — vault 7.9.2009 (Aliyun)
[base]
name=CentOS-7.9.2009 - Base
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/os/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
enabled=1

[updates]
name=CentOS-7.9.2009 - Updates
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/updates/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
enabled=1

[extras]
name=CentOS-7.9.2009 - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/extras/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
enabled=1
```

**方案 B：官方 vault.centos.org（境外或备用）**

把上面各 `baseurl=` 中的主机改为：

`https://vault.centos.org/7.9.2009/...`（路径结构相同：`os`、`updates`、`extras`）。

**3）清理缓存并测源**

```bash
sudo yum clean all
sudo yum repolist
```

若仍有其它 `.repo` 指向已失效域名，可临时 **`enabled=0`** 或移出该文件再测。

---

## 四、若 `yum` 仍因 `pycurl` / `CRYPTO_num_locks` 失败

**现象：** `import pycurl` 报错 **`undefined symbol: CRYPTO_num_locks`**，多为 **OpenSSL / libcurl** 与 **python-pycurl** 版本不一致。

**优先（yum 已可用时）：**

```bash
sudo yum reinstall -y python python-libs python-pycurl curl libcurl openssl openssl-libs
```

**yum 仍不能用时：** 用 **rpm** 从 **vault** 下载与系统一致的 **`python-pycurl`** 再安装（架构一般为 `x86_64`）：

```bash
cd /tmp
ARCH=$(uname -m)
VAULT_BASE="https://mirrors.aliyun.com/centos-vault/7.9.2009/os/${ARCH}/Packages"
# 若 404，打开目录页核对 python-pycurl 的准确 rpm 文件名
RPM="python-pycurl-7.19.0-19.el7.${ARCH}.rpm"
wget "${VAULT_BASE}/${RPM}" -O "${RPM}"
sudo rpm -Uvh --replacepkgs "${RPM}"
/usr/bin/python2 -c "import pycurl; print('pycurl ok')"
sudo yum --version
```

更细的步骤与故障表见同目录：**[CentOS7-修复yum与Git.md](./CentOS7-修复yum与Git.md)**。

---

## 五、安装 `sqlite-devel`（编译自装 Python 时需要）

```bash
sudo yum install -y sqlite-devel
```

若你**从源码编译** Python 3.10+，务必在编译前已安装 **`sqlite-devel`**，否则会出现 **`_sqlite3` 缺失**。

---

## 五（重要）、本仓库需要 Python 3.10+，不能用 yum 自带的 3.6

**README 与 `requirements.txt` 要求 Python 3.10+。**  
CentOS 7 上 `yum install python3` 得到的是 **Python 3.6**，无法满足 **`httpx>=0.25`**、**`pydantic>=2`** 等依赖，会出现：

`No matching distribution found for httpx>=0.25.0`

**可选做法（任选其一）：**

### A）Software Collections（SCL）— `rh-python311`（常见）

```bash
sudo yum install -y centos-release-scl
sudo yum install -y rh-python311 rh-python311-python-devel
# 解释器路径（固定）：
/opt/rh/rh-python311/root/usr/bin/python3 --version
/opt/rh/rh-python311/root/usr/bin/python3 -c "import sqlite3; print('sqlite3 ok')"
```

### B）自编译 `/usr/local` Python 3.11

先 `yum install -y sqlite-devel openssl-devel bzip2-devel ...`，再按官方文档编译；装好后确认：

```bash
/usr/local/bin/python3.11 -c "import sqlite3; print('ok')"
```

### C）其它来源

如 **IUS**、**pyenv**、容器镜像等，只要 **`python3 --version` ≥ 3.10** 且 **`import sqlite3` 成功**即可。

---

## 六、部署本仓库：用 3.10+ 重建 venv

在克隆下来的项目目录（如 `/opt/qurl-bot-slack`），**把下面的 `PY311` 换成你机器上实际的 3.10+ 路径**（SCL 示例已给出）：

```bash
sudo systemctl stop qurl-bot-slack 2>/dev/null || true
cd /opt/qurl-bot-slack

PY311=/opt/rh/rh-python311/root/usr/bin/python3
# 或: PY311=/usr/local/bin/python3.11

sudo rm -rf venv
sudo "$PY311" -m venv venv
sudo ./venv/bin/pip install -U pip
sudo ./venv/bin/pip install -r requirements.txt

sudo systemctl start qurl-bot-slack
sudo systemctl status qurl-bot-slack
```

**原则：** 不要用 **`/usr/bin/python3`（3.6）** 建 venv；`which python3` 若指向 **`/usr/local`** 且无 **`_sqlite3`**，应先按第五节修好解释器再建 venv。

---

## 七、`git clone` HTTPS 报错（HTTP/2）

```bash
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000
git clone https://github.com/haochangjiu/qurl-bot-slack.git
```

或使用 **SSH**（需配置 GitHub 公钥）：

```bash
git clone git@github.com:haochangjiu/qurl-bot-slack.git
```

---

## 八、一键部署脚本（源与 yum 正常后）

在项目根目录：

```bash
sudo bash deploy.sh
```

`deploy.sh` 会优先选择 **Python 3.10+ 且带 `sqlite3`** 的解释器创建 venv（含 SCL、`/usr/local` 等常见路径）。

---

## 九、顺序小结（建议按此顺序执行）

| 顺序 | 动作 |
|------|------|
| 1 | 确认 `python` → 2.7，`yum` 不再被 Python 3 执行 |
| 2 | 修复或替换 **`CentOS-Base.repo`** 为 **vault** |
| 3 | `yum clean all && yum repolist` |
| 4 | 若仍失败，按第四节修 **pycurl** / **openssl** |
| 5 | `yum install -y sqlite-devel`；另装 **Python 3.10+**（如 **SCL rh-python311**），勿依赖 yum 自带 3.6 |
| 6 | 用 **3.10+ 解释器**（如 `/opt/rh/rh-python311/root/usr/bin/python3`）**`-m venv`** 并 `pip install -r requirements.txt` |
| 7 | `git` 克隆失败时改 **HTTP/1.1** 或 **SSH** |

---

*镜像与 RPM 文件名可能随时间调整；若某 URL 404，请打开对应 vault 目录页核对真实包名与路径。*
