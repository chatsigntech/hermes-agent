# `tiago.chatsign.ai` Cloudflare Tunnel SSH 配置手册

这份文档用于在**另一台服务器**上配置 `tiago.chatsign.ai`，使其可以通过 Cloudflare Tunnel 提供 SSH 访问。

目标效果：
- 服务器端通过 `cloudflared` 暴露 `ssh://localhost:22`
- DNS 域名固定为 `tiago.chatsign.ai`
- 客户端通过 `cloudflared access ssh --hostname tiago.chatsign.ai` 登录

重要原则：
- **不要复用当前机器已有的 tunnel 凭证 JSON**
- **只复制 Cloudflare 登录证书 `cert.pem`，或者在目标机重新执行 `cloudflared tunnel login`**
- 本文默认目标机是 **Ubuntu / Debian**

---

## 0. 需要准备的信息

先把下面几个值确定好：

```bash
TARGET_USER="<目标服务器用户名>"
TARGET_HOST="<目标服务器IP或可SSH登录的主机名>"
SSH_DOMAIN="tiago.chatsign.ai"
TUNNEL_NAME="tiago-ssh"
```

示例：

```bash
TARGET_USER="ubuntu"
TARGET_HOST="1.2.3.4"
SSH_DOMAIN="tiago.chatsign.ai"
TUNNEL_NAME="tiago-ssh"
```

---

## 1. 从当前机器复制 Cloudflare 认证证书

在**当前这台机器**上执行下面命令，把 Cloudflare 登录证书复制到目标服务器：

```bash
ssh "${TARGET_USER}@${TARGET_HOST}" "mkdir -p ~/.cloudflared && chmod 700 ~/.cloudflared"
scp ~/.cloudflared/cert.pem "${TARGET_USER}@${TARGET_HOST}:~/.cloudflared/cert.pem"
ssh "${TARGET_USER}@${TARGET_HOST}" "chmod 600 ~/.cloudflared/cert.pem"
```

说明：
- 当前机器上的 Cloudflare 登录证书路径是：
  - `~/.cloudflared/cert.pem`
- **不要复制**当前机器上已有的 tunnel 凭证 JSON
- 目标机后面会创建自己的新 tunnel 和新的 `<UUID>.json`

如果你不想复制 `cert.pem`，也可以跳过这一步，改为在目标服务器上执行：

```bash
cloudflared tunnel login
```

然后在浏览器里登录并授权 `chatsign.ai`。

---

## 2. 在目标服务器安装 `cloudflared`

在**目标服务器**上执行：

```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

如果 `dpkg` 报依赖问题，再执行：

```bash
sudo apt-get update
sudo apt-get install -f -y
```

---

## 3. 在目标服务器创建新的 tunnel

在**目标服务器**上执行：

```bash
cloudflared tunnel create tiago-ssh
```

执行成功后会输出一个 tunnel UUID，并且自动生成：

```bash
~/.cloudflared/<UUID>.json
```

请把输出中的 UUID 记下来，下面称为：

```bash
TUNNEL_UUID="<这里替换成上一步输出的 UUID>"
```

示例：

```bash
TUNNEL_UUID="12345678-1234-1234-1234-123456789abc"
```

---

## 4. 写入目标服务器的 Cloudflare Tunnel 配置

在**目标服务器**上创建 `~/.cloudflared/config.yml`：

```bash
cat > ~/.cloudflared/config.yml <<'YAML'
tunnel: TUNNEL_UUID_PLACEHOLDER
credentials-file: /home/TARGET_USER_PLACEHOLDER/.cloudflared/TUNNEL_UUID_PLACEHOLDER.json

ingress:
  - hostname: tiago.chatsign.ai
    service: ssh://localhost:22
  - service: http_status:404
YAML
```

然后把占位符替换掉：

```bash
sed -i "s/TUNNEL_UUID_PLACEHOLDER/${TUNNEL_UUID}/g" ~/.cloudflared/config.yml
sed -i "s/TARGET_USER_PLACEHOLDER/${USER}/g" ~/.cloudflared/config.yml
cat ~/.cloudflared/config.yml
```

如果目标机 SSH 不是 22 端口，把：

```yaml
service: ssh://localhost:22
```

改成真实端口，例如：

```yaml
service: ssh://localhost:2222
```

---

## 5. 为 `tiago.chatsign.ai` 添加 DNS 路由

在**目标服务器**上执行：

```bash
cloudflared tunnel route dns tiago-ssh tiago.chatsign.ai
```

执行后，Cloudflare 会把 `tiago.chatsign.ai` 指向这个新 tunnel。

如果这一步报错说记录已经存在，先不要强行覆盖，先去 Cloudflare Dashboard 检查：
- `tiago.chatsign.ai` 是否已经被别的服务占用
- 是否已经指向别的 tunnel

---

## 6. 把 cloudflared 配成守护服务

在**目标服务器**上执行：

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yml /etc/cloudflared/config.yml
sudo cp ~/.cloudflared/${TUNNEL_UUID}.json /etc/cloudflared/
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

如果 `service install` 已经做过，也可以直接：

```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
```

---

## 7. 检查目标服务器本地 SSH 服务

在**目标服务器**上执行：

```bash
ssh localhost
```

或者至少执行：

```bash
nc -z localhost 22
```

如果这里都不通，说明问题不在 Cloudflare，而在目标服务器自己的 SSH 服务。

如果 SSH 端口不是 22，也请对应修改前面的 `config.yml`。

---

## 8. 从客户端配置 SSH 登录

在**客户端机器**上安装 `cloudflared`：

### macOS
```bash
brew install cloudflare/cloudflare/cloudflared
```

### Linux
```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
```

然后在客户端的 `~/.ssh/config` 里加入：

```sshconfig
Host tiago.chatsign.ai
    HostName tiago.chatsign.ai
    User <目标服务器用户名>
    ProxyCommand cloudflared access ssh --hostname %h
```

如果要绑定 SSH key，再改成：

```sshconfig
Host tiago.chatsign.ai
    HostName tiago.chatsign.ai
    User <目标服务器用户名>
    IdentityFile ~/.ssh/<你的私钥文件>
    IdentitiesOnly yes
    ProxyCommand cloudflared access ssh --hostname %h
```

如果你不想影响现有全局 host，也可以用别名：

```sshconfig
Host tiago-remote
    HostName tiago.chatsign.ai
    User <目标服务器用户名>
    ProxyCommand cloudflared access ssh --hostname %h
```

这样以后用：

```bash
ssh tiago-remote
```

---

## 9. 客户端验证

### 交互式验证

```bash
ssh tiago.chatsign.ai
```

### 非交互式验证

如果已经完成 SSH key 登录配置，可以执行：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 tiago.chatsign.ai 'echo __SSH_OK__'
```

成功时应输出：

```text
__SSH_OK__
```

---

## 10. 常见问题判断

### 情况 A：提示 `Permission denied`

说明：
- Cloudflare Tunnel 基本通了
- 但 SSH 认证没准备好

处理：
- 检查远端 `~/.ssh/authorized_keys`
- 检查客户端 `IdentityFile`
- 检查 `User`

### 情况 B：提示 `Connection closed by UNKNOWN port 65535`

说明：
- 常见于 `cloudflared access ssh` 首连不稳定
- 或 Cloudflare Access 会话还没准备好

处理：
- 重试 1 到 2 次
- 单独运行：

```bash
cloudflared access ssh --hostname tiago.chatsign.ai
```

- 再重新执行 `ssh`

### 情况 C：超时 / No route to host

说明：
- DNS、Tunnel、网络路径或服务器本地 SSH 可能有问题

处理：
- 检查 DNS 是否已经路由到 tunnel
- 检查 `cloudflared` 服务是否在目标服务器上运行
- 检查 `localhost:22` 是否可达

---

## 11. 最终检查清单

目标服务器上应满足：

```bash
cloudflared tunnel list
cloudflared tunnel info tiago-ssh
cat ~/.cloudflared/config.yml
sudo systemctl status cloudflared --no-pager
```

客户端上应满足：

```bash
cloudflared --version
ssh tiago.chatsign.ai
```

---

## 12. 关键结论

这套配置的关键点是：

- 域名固定为：`tiago.chatsign.ai`
- tunnel 名称建议固定为：`tiago-ssh`
- 认证信息只需要：
  - 当前机器上的 `~/.cloudflared/cert.pem`
  - 或者在目标机重新执行 `cloudflared tunnel login`
- **不要复制当前机器已有 tunnel 的 `<UUID>.json`**
- 目标机应该创建自己的新 tunnel 和新的凭证 JSON

