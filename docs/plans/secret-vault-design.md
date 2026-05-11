# hermes 保险箱（Vault）设计 v5

> **中文叫法**：保险箱（vault）
> **定位**：用户**私人重要信息**的加密存储库（银行卡、护照、私人邮箱密码、会员账号等），**跟 hermes 平行独立**，不替代 hermes 自己的 .env / token 体系。
>
> 状态：v5.1 草案（v5 review 修订）
> 作者：Claude（在 chatsign 指导下）
> 日期：2026-05-11
>
> 修订历史：
> - v1-v4.2 (2026-05-10) 错误定位为"hermes secret 加密替代"，过度复杂
> - v5 (2026-05-11) **根本重写**：定位变更为"用户私人信息保险箱"，跟 hermes 平行
> - v5.2 (2026-05-11) Phase 0.5 实测后修订 + pure design 决策完成：
>   - 7 个 pure design 决策完成（D-16~D-22）
>   - Phase 0.5 实测：B1 ✅ hermes 完全支持 url MCP / B2 ⚠️ clientInfo 不可靠 → URL `?client=` 主依据 / D2 ✅ hermes 容错健壮但有"3 次后永久放弃"隐患
>   - D-12 修订（caller 区分主依据改为 URL）
>   - D-22 修订（端口冲突 abort 启动，不 fallback 随机——因为 hermes config 写死 url）
>   - 新增 D-23（launchd 启动顺序约束）+ D-24（可选 hermes 上游 PR）
>   - §5.2 加启动顺序约束章节
>   - Phase 0.5 标 ✅ 完成
>
> - v5.1 (2026-05-11) review 修订：
>   - **MCP 协议从 stdio 改 HTTP/SSE**（B1：stdio 跟 daemon 不兼容）
>   - **删除 fallback redactor 整章**（H3：过度设计，capability 设计纪律即够）
>   - audit log caller 区分机制明确（B2：URL path token 约定 + MCP init metadata）
>   - vault lock 时 in-flight capability 处理策略（H1：走完 + 拒新）
>   - brute force throttling：daemon 启动 30s cool-down + 失败计数持久化（H2）
>   - vault 自己的 `~/.hermes/vault.yaml` 配置（H4：跟 hermes .env 解耦）
>   - capability 工具扩展机制（M3：用户目录 `~/.hermes/vault_capabilities/`）
>   - vault-unlock.sock → **vault-control.sock**（M4：命名误导）
>   - daemon crash 风险 + IM 告警（M5）
>   - 备份提示支持"已备份"或英文（M6）
>   - 工作量微调：3.5 天 → **4 天**
>
> v4.2 / v5 历史可见 git log。

---

## 1. 背景

### 1.1 现状

hermes 自己的 secret（EMAIL_PASSWORD / TELEGRAM_BOT_TOKEN 等）当前由
`~/.hermes/.env` + `gateway/config.py:_apply_env_overrides()` 体系管理，
跑得稳定，**v5 不动这条**。

### 1.2 v5 定位（关键）

**vault 不是 hermes secret 的替代，而是用户私人重要信息的独立保险箱**。

| 内容 | 存哪 | 谁消费 |
|---|---|---|
| EMAIL_PASSWORD（hermes 用来收邮件） | `~/.hermes/.env` | hermes 进程 |
| TELEGRAM_BOT_TOKEN（hermes bot） | `~/.hermes/.env` | hermes 进程 |
| 用户身份证号 / 护照号 | **vault** | 用户自己查、hermes capability 偶尔代办 |
| 用户银行卡号 / 支付密码 | **vault** | 同上 |
| 用户私人 Gmail 密码（不是 hermes 的） | **vault** | 用户自己查 |
| 用户 1Password / iCloud 恢复密钥 | **vault** | 用户自己查 |
| 用户会员账号 / 飞行常客号 | **vault** | hermes capability 自动查询积分 |

### 1.3 用户提出的目标（重新理解后）

1. 加密存储用户的核心机密信息
2. 启动时输入主密码解锁，仅内存
3. 解密后内容不在日志、对话中显式出现
4. **跟 hermes 平行独立，对 hermes 主版本侵入最小**（v5 实现：0 嵌入）
5. **hermes 知道 vault 存在**，能查清单（不能查值），用得着时通过 capability 调
6. **未来 hermes 升级有官方脱敏机制时，我们的 fallback 优雅退出**

---

## 2. 威胁模型

### 2.1 范围内（必须防）

| 威胁 | 来源 |
|---|---|
| **T1** vault.age 文件失窃后离线读取 | iCloud / Time Machine / 备份盘 |
| **T2** 同 mac 其他登录账户读取 vault | 多用户场景 |
| **T3** Claude Code 误读 vault.age 写入对话 jsonl | 已发生过类似事故 |
| **T4** Claude Code 把 vault 内容拷贝/转述到 LLM 上下文 | 用户偷懒在对话里说密码 |
| **T5** vault daemon 自身日志意外打印明文 | 实现 bug |
| **T6** vault 内容被 hermes capability 消费时漏到 hermes log | **由 capability 设计纪律防御**（v5.1 不再装 redactor）|
| **T7** 对话内容上传 LLM 服务后被持久化 | 公理 I-4 防 |
| **T8** vault.age 半坏 / 写盘中断锁死 | 电源故障 |
| **T9** 弱主密码 | UX 失败 |

### 2.2 范围外（明确不防）

| 威胁 | 原因 |
|---|---|
| **N1** root / 物理改 vault 二进制 | 物理可达即终局 |
| **N2** 同 UID 进程 attach lldb | 同 UID 即等价控制 |
| **N3** 全系统沦陷 | OS 层威胁 |
| **N4** swap 落盘 | macOS swap 默认加密 |
| **N5** 用户主密码键盘记录 | 用户终端可信 |

### 2.3 不变量（设计公理）

- **I-1**：vault 明文内容不出现在持久化或上传载体
- **I-2**：vault 明文仅存在于 vault daemon 进程内存
- **I-3**：主密码仅交互式 prompt 输入，不持久化
- **I-4**：Claude / hermes 跟 vault 交互必须假设通信会被持久化 → vault 永不返回字面值（除用户主动 `vault show`）

---

## 3. 设计原则

| # | 原则 | 含义 |
|---|---|---|
| **P1** | Capability over Disclosure | vault 提供"用此条做事"的能力，不返回值 |
| **P2** | **Zero hermes intrusion** | hermes 主代码 0 行改动；仅 config.yaml 加一节 MCP |
| **P3** | Fail closed | 解密失败 / vault 缺失 → 拒绝启动（vault daemon），但 hermes 不受影响 |
| **P4** | Auditability | 每次取 vault 内容记 audit log（仅元数据，不记值）|
| **P5** | Standard crypto only | age + Argon2id，不自实现 |
| **P6** | Graceful coexistence | 未来 hermes 加官方功能时 vault 自动让位 |

---

## 4. 架构总览

```
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  hermes daemon                │  │  vault daemon                 │
│  (照常用 .env, 不改)          │  │  (独立进程，独立 launchd plist)│
│                              │  │                              │
│   - email / telegram / weixin │  │   - 持有解密的 KV in memory   │
│     用 .env 里的 token        │  │   - vault.age (磁盘密文)      │
│   - subprocess 照常           │  │   - unlock socket             │
│   - 配置 mcp_servers.vault    │  │   - web unlock (本地+远程)    │
│   - 通过 MCP client 自动发现  │  │   - 暴露 stdio MCP server     │
└──────────────┬───────────────┘  └──────────────┬───────────────┘
               │                                 │
               └──────────┬──────────────────────┘
                          │ 都连同一个 vault MCP server
                          │
                   ┌──────▼──────┐
                   │ Claude Code │
                   │ (也配 MCP)  │
                   └─────────────┘
```

### 4.1 关键架构决策

| # | 决策 | 选定 | 拒绝的备选 |
|---|---|---|---|
| **D-1** | hermes 跟 vault 关系 | **平行独立** | 嵌入式（v4.2 错误方向）|
| **D-2** | hermes 发现 vault | **MCP client + config.yaml**（hermes 已有此机制） | python *.pth 自动加载 / cli.py 嵌入 |
| **D-3** | LOCKED 状态 MCP 行为 | **MCP success + payload `{vault_locked: true, hint: "..."}`**（v5.1 明确）| MCP error / 拒连 |
| **D-4** | vault 启动方式 | **独立 launchd plist**，不依赖 hermes | 嵌入 hermes 进程 |
| **D-5** | 主密码输入 UX | **三通道**：A socket / B web 本地 / C web 远程经 tunnel | 单一前台 prompt |
| **D-6** | 通道 C 加密 | **X25519 + XChaCha20-Poly1305**（tweetnacl-js） | RSA-OAEP / 不加密走 HTTPS |
| **D-7** | 通道 C 默认开关 | **检测 `vault.yaml` 中 `remote_hostname` 设置即启** + 首次启用强制告警 | 全开 / 全关 |
| **D-8** | 脱敏机制（v5.1 重定向）| **依赖 capability 设计纪律**（capability 不返回字面值；vault show 在用户终端只在用户屏幕）| ~~v5 fallback redactor~~（删除：过度设计）|
| **D-9** | unlock 告警 | wechat + telegram 双推 | 仅 audit log |
| **D-10** | tunnel 实现 | cloudflare（当前），**tunnel-agnostic** 易换 tailscale | 绑死 cloudflare |
| **D-11** | MCP 协议（v5.1 新）| **HTTP/SSE**（vault daemon 暴露，多 client 直连）| stdio（被否决：每 client 启动独立 server 子进程，跟 daemon 模式冲突）|
| **D-12** | audit log caller 区分（v5.1 review 后修订）| **主依据 URL `?client=` 约定**（hermes 配 `?client=hermes`，claude 配 `?client=claude`）；clientInfo 仅辅助记录。**实测确认 hermes mcp_tool 默认上报 `clientInfo: "mcp/0.1.0"` 通用默认，不能用作主依据**。**约定非强认证** | clientInfo 优先 (v5.1 初稿) — Phase 0.5 实测否决 |
| **D-13** | brute force throttling（v5.1 新）| daemon 启动后 30s cool-down + 失败计数持久化 `~/.hermes/vault.failcount` | 仅靠 launchd KeepAlive |
| **D-14** | vault 配置文件（v5.1 新）| `~/.hermes/vault.yaml`（vault 自己的，不复用 hermes .env） | 共用 hermes .env |
| **D-15** | capability 扩展（v5.1 新）| 用户目录 `~/.hermes/vault_capabilities/*.py` 自动扫描注册 | 全部 vault 内置 / hardcoded |
| **D-16** | X25519 私钥策略（v5.1 review）| **首次生成 + 永久持久化到 vault.unlock.privkey 0600**。公钥 fingerprint 不变，用户只首次对比 | 每次启动重生成（fingerprint 频繁变化 UX 差） / KDF 派生（主密码轮换连锁问题） |
| **D-17** | launchd plist 类型（v5.1 review）| **LaunchAgent**（用户态）：~/Library/LaunchAgents/ai.hermes.vault.plist。用户登出自动清内存 vault | LaunchDaemon (root)：跨用户共享、需 sudo、Touch ID 集成难 |
| **D-18** | LOCKED 时 list_tools 行为（v5.1 review）| **仅返回控制类工具**：vault_status / vault_unlock_hint。unlock 后客户端重新 list_tools 见全部 capabilities | 返回完整列表（agent 反复试错调用）/ 返回空（agent 看不到 vault 存在）|
| **D-19** | control socket LOCKED 命令白名单（v5.1 review）| **控制类**（unlock/lock/status/reset-failcount）可用；**数据类**（set/show/list/delete/rotate/import）拒绝返回 "vault locked" | 全开 / 全拒 |
| **D-20** | vault.yaml 改动生效方式（v5.1 review）| **重启 daemon** 才生效。`hermes-vault restart` 或 launchctl reload | hot-reload（watchdog 复杂、字段语义不一致）|
| **D-21** | audit log rotation（v5.1 review）| **vault 内置 rolling**：超 10MB 或 90 天翻新，保留最近 12 份 | 依赖 macOS newsyslog / 不管 |
| **D-22** | MCP 端口策略（Phase 0.5 后修订）| **vault.yaml 配置端口，默认 7860，冲突时 abort 启动让用户改**。原 v5.1 方案"fallback 随机 + 写 vault-port 文件"被否决，因为 hermes config.yaml 写死 url，端口变化用户无法跟随 | 固定无配置 / 自动 fallback（hermes config 跟不上）|
| **D-23** | hermes/vault 启动顺序（Phase 0.5 新）| **vault launchd plist 必须 `RunAtLoad=true`** 且 hermes 启动前已 ready；hermes mcp_tool 实测 3 次初始重试（backoff 1+2+4s≈15s），超时永久放弃直到 config.yaml 改动 hot-reload。vault.yaml 改动也触发 hermes mcp_tool 重连 | 不保证顺序（hermes 启动太早 → 永远看不到 vault 工具）|
| **D-24** | hermes-vault 上游 PR（可选，Phase 0.5 后新）| 给 hermes 提小 PR：`ClientSession(..., client_info=Implementation(name="hermes-agent", version=...))`。让 clientInfo 有意义，不阻塞 vault 开工 | 不上游（永远依赖 URL 约定） |

---

## 5. 组件详解

### 5.1 vault.age 文件格式

**单一密文文件** `~/.hermes/vault.age`：

```json
// 解密后
{
  "version": 1,
  "created_at": "2026-05-11T...",
  "rotated_at": "2026-05-11T...",
  "secrets": {
    "personal/ID_CARD":    {"value": "...", "kind": "id"},
    "personal/PASSPORT":   {"value": "...", "kind": "id"},
    "banking/ICBC":        {"value": {"card": "...", "phone": "..."}, "kind": "bank_card"},
    "accounts/PERSONAL_GMAIL": {"value": "...", "kind": "password"},
    ...
  }
}
```

`name` 用 `category/key` 形式便于按类查询。

**加密**：age + scrypt（passphrase 模式），`pyrage` Python binding。

### 5.1.1 文件权限 + 完整性

| 路径 | 权限 | 启动时检查 |
|---|---|---|
| `~/.hermes/` | 0700 | ✅ 不对则拒启 |
| `~/.hermes/vault.age` | 0600 | ✅ |
| `~/.hermes/vault.age.bak.<ts>` | 0600 | ✅ 同上 |
| `~/.hermes/vault.unlock.pubkey` | 0644（公钥） | ✅ |
| `~/.hermes/vault.unlock.privkey` | 0600 | ✅ |
| `~/.hermes/vault-control.sock` | 0600 | ✅（创建时设定，vault CLI 与 daemon 通信）|
| `~/.hermes/vault-audit.log` | 0600 | ✅ |
| `~/.hermes/vault.yaml` | 0600 | ✅（v5.1 新：vault 自己的配置）|
| `~/.hermes/vault.failcount` | 0600 | ✅（v5.1 新：跨重启失败计数持久化）|

### 5.1.2 atomic write + 滚动备份

```
write_vault(new_data, passphrase):
    tmp = vault.age.tmp.<random>
    age_encrypt(...) → tmp
    fsync(tmp)
    cp vault.age → vault.age.bak.<ts>  # 保留最近 5 份
    rename(tmp, vault.age)
    fsync(parent_dir)
```

### 5.1.3 主密码强度强制

`vault init` / `vault rotate-passphrase` 时：
- 长度 ≥ 12
- zxcvbn score ≥ 3
- 弱密码直接拒绝

### 5.1.4 备份提示（vault init 强制）

```
$ vault init
Master password: ************
Confirm:         ************
Strength: ✓ score=4
[OK] vault created.

⚠️  CRITICAL: Backup these two things NOW.
   1. Save master password to a password manager
   2. Copy ~/.hermes/vault.age to OFFLINE medium

已经备份好两样了吗？请输入 "已备份" 或 "yes I backed up both" 继续: _
```

### 5.2 vault daemon

独立 Python daemon，由独立 launchd plist 拉起：

```
~/Library/LaunchAgents/ai.hermes.vault.plist  (新增)
   ProgramArguments: python -m hermes_vault.daemon
```

启动序列（v5.1 修订）：

```
T+0    launchd 拉起 hermes_vault.daemon
T+1s   daemon:
         a) 加载 ~/.hermes/vault.yaml (D-14)
         b) 检查 vault.age 文件存在 + 权限 0600（不对则 abort）
         c) 起 unix socket: ~/.hermes/vault-control.sock (D-12)
         d) 起 HTTP/SSE MCP server: 监听 127.0.0.1:7860 (D-11)
         e) 进入 LOCKED 状态：
            - 不解密 vault.age
            - MCP 工具响应 success+payload {vault_locked: true, hint: "..."}
T+1s   加载 ~/.hermes/vault.failcount，若失败计数已超阈值（如 10）→ 拒绝 unlock 请求
T+2s   daemon ready，状态机：vault: LOCKED
       cool-down 30 秒（D-13）：拒绝 unlock 请求，返回 "throttled, retry in Ns"

T+32s  cool-down 结束，开始接受 unlock
T+?    $ hermes-vault unlock (or via web)
       → daemon 解密 → 内存持有 KV → 状态切到 RUNNING
       → 重置 vault.failcount = 0
       → 推 wechat + telegram 告警 "vault unlocked from IP X"
```

vault daemon **完全独立**，跟 hermes 进程无任何 IPC 依赖。
hermes 当作"另一个 MCP server"使用。

**MCP 协议为 HTTP/SSE**（v5.1 改自 stdio）：vault daemon 单实例对外服务，
hermes / Claude Code 都是 client，直连 `http://127.0.0.1:7860/mcp`。
stdio MCP 因为每 client spawn 独立 server 进程，跟 daemon 模式不兼容。

### 5.2.1 启动顺序约束（D-23，Phase 0.5 后新增）

**vault daemon 必须在 hermes daemon 启动之前 ready**。理由：

实测 hermes mcp_tool 容错（Phase 0.5）：
- 初次连不上 → 3 次重试，指数 backoff（1+2+4s ≈ 15s 内）
- 3 次失败 → **永久放弃**，hermes 看不到 vault 工具
- 唯一恢复路径：用户改 `config.yaml` 触发 hot-reload（hermes 每 5s stat 此文件）

→ **vault plist `RunAtLoad=true`**（启动时立即拉起）+ **hermes 启动前 vault 至少 socket listen ready**（LOCKED 状态也算 ready，能响应 init / list_tools）。

具体保证方式：
- vault plist 路径：`~/Library/LaunchAgents/ai.hermes.vault.plist`
- hermes 自己的 plist 不依赖 vault → 各自启动，靠"vault 启动快"概率保证
- 极端情况（vault 启动失败 ≥15s）→ 用户重启 hermes 或改 config.yaml 任意字段触发 hot-reload

### 5.3 三通道 Unlock

| 通道 | 命令 | 适用场景 | 安全级别 |
|---|---|---|---|
| **A. socket prompt** | `hermes-vault unlock` | ssh 进 mac mini | 最高（不经任何网络）|
| **B. web 本地** | `hermes-vault unlock --web` | 本地浏览器 / ssh tunnel | 高（仅本机内核）|
| **C. web 远程** | `hermes-vault unlock --web --remote` | 外面手机 / 笔记本 | 中（依赖 tunnel + 客户端加密）|

### 5.3.1 通道 A: Socket Prompt

```
$ hermes-vault unlock
Master password: ***********  ← getpass，不回显
[OK] vault is RUNNING. notified wechat + telegram.
```

实现：unix socket peer 检查（macOS `LOCAL_PEERCRED`，需手写 `SOL_LOCAL=0`）+ UID 必须匹配 daemon UID。

### 5.3.2 通道 B: Web 本地

```
$ hermes-vault unlock --web
[vault] Web unlock listener on http://127.0.0.1:54321
[vault] Open: http://127.0.0.1:54321/unlock?n=abc...
[vault] Remote: ssh -L 54321:localhost:54321 mac-mini
[vault] Waiting (5 min timeout)...
```

仅 127.0.0.1 监听，浏览器或 ssh tunnel 后访问。

### 5.3.3 通道 C: Web 远程经 tunnel

详见 §5.5。

### 5.3.4 主动重锁（v5.1 明确 in-flight 行为）

```
$ hermes-vault lock
[lock] in-flight capability calls: 2 (will complete normally)
[lock] new calls will be rejected
[OK] vault re-locked. KV cleared from memory after in-flight completes.
```

策略：
- **新调用立即拒绝**：返回 `{vault_locked: true, hint: "..."}`
- **已发起的 capability 调用走完**（不强制中断，避免 partial state）
- 所有 in-flight 完成后真正清空 KV 内存

### 5.3.5 brute force 保护（v5.1 加 throttling）

3 道防线：

1. **每次启动 30s cool-down**：daemon ready 后强制 sleep 30 秒才接受 unlock，
   阻止"快速重启-试 3 次"的紧密循环
2. **失败计数持久化** `~/.hermes/vault.failcount`：跨进程重启累积
3. **阈值锁定**：失败 10 次 → daemon 启动后立即拒绝 unlock 1 小时
   （需要用户手动 `vault reset-failcount` 解除）

成功 unlock 后失败计数归零。

启用单次 daemon 实例的"3 次错密码自杀"作为最后一层。

### 5.4 vault MCP server

vault daemon 暴露 **HTTP/SSE MCP server**（D-11，v5.1），hermes 和 Claude Code **都把它当成第三方 MCP**，直连同一个 daemon。

#### 5.4.1 hermes 端集成（0 嵌入）

`~/.hermes/config.yaml` 加：

```yaml
mcp_servers:
  vault:
    url: "http://127.0.0.1:7860/mcp?client=hermes"   # ?client=hermes 给 audit log 用
    auth: none
    description: "User personal information vault"
```

hermes 现有 `tools/mcp_tool.py` 启动时自动连，发现工具列表，agent 调用即可。

**hermes 主代码 0 行改动**——这是 v5 跟 v4.2 最大的区别。

⚠️ Phase 0 补测：确认 hermes 的 mcp_servers config 支持 `url` 形式（HTTP/SSE）。
若 hermes 当前只支持 stdio，需要先给 hermes 加 HTTP MCP client 支持
（这是上游通用功能，可独立提 PR）。

#### 5.4.2 Claude Code 端集成

`~/.claude/mcp_servers.json`（如有）或 Claude Code 配置加：

```json
{
  "mcpServers": {
    "vault": {
      "url": "http://127.0.0.1:7860/mcp?client=claude"
    }
  }
}
```

#### 5.4.3 工具清单

```
vault_list(category?: str) → [{"name": str, "kind": str, "category": str}]
   # 列名字 + kind，不列值

vault_status(name: str) → {
    "set": bool,
    "kind": str,
    "length": int,
    "sha256_prefix": str,    # 前 8 字符
    "masked": str,           # 例 "****1234" for card
    "last_used_seconds_ago": int | null
}

# v5.1: capability 工具来自两个来源
#   - 内置 (hermes_vault/capabilities/*.py)
#   - 用户自定义 (~/.hermes/vault_capabilities/*.py)，daemon 启动时自动扫描注册
#
# 例如内置：
#   query_bank_balance(bank: str) → {balance, currency, as_of}
# 例如用户自定义：
#   query_my_membership_points(brand: str) → {points, level, expiry}
#
# 所有 capability 永不返回 vault 字面值（公理 I-4）

# ❌ 永不实现
vault_get(name) → str
vault_dump() → dict
```

#### 5.4.4 LOCKED 状态响应格式（v5.1 明确为 MCP success）

MCP 工具调用返回 **success + payload**（不是 error）：

```json
// MCP tool response (success path)
{
  "content": [{
    "type": "text",
    "text": "{\"vault_locked\": true, \"hint\": \"Vault is locked. Run `hermes-vault unlock` (local), `--web` (browser), or `--web --remote` (cloudflare).\", \"since\": \"2026-05-11T08:00:00Z\"}"
  }]
}
```

理由：error 会触发 MCP client 重试逻辑；success+payload 让 agent 自己判断。

agent 看到 `vault_locked: true` 应**直接告知用户**而不是反复重试。

#### 5.4.5 audit log（v5.1 caller 区分机制）

每次工具调用记录：

```
2026-05-11T12:34:56  caller=hermes  tool=vault_list  category=banking  ok
2026-05-11T12:35:01  caller=claude  tool=vault_status  name=BANK_CMB  ok
2026-05-11T12:36:30  caller=hermes  tool=query_bank_balance  bank=CMB  ok  duration=1.2s
2026-05-11T12:40:00  caller=unknown tool=vault_get          ok=false  reason=tool_not_implemented
```

**caller 来源**（D-12，Phase 0.5 实测修订）：
1. **主依据**：URL query string `?client=hermes` / `?client=claude`（用户在 config 里写）
2. **辅助记录**：MCP initialization 阶段 client 自报的 `clientInfo.name`（hermes 实际报 `"mcp/0.1.0"` 通用默认，不可靠，仅作 trace 用）
3. **兜底**：`unknown`

**实测发现**（Phase 0.5）：hermes mcp_tool.py 实例化 ClientSession 时不传 client_info，
SDK fallback 到 `Implementation(name="mcp", version="0.1.0")`，跟其他默认 MCP client
撞名——**clientInfo 不能作为区分依据**，必须靠 URL 约定。

audit log 的 caller 字段 = 责任追溯辅助工具，**不是 access control 依据**（攻击者能伪造 URL ?client=）。

#### 5.4.6 capability 工具扩展机制（v5.1 新）

vault daemon 启动时扫描两个目录：

```
hermes_vault/capabilities/        ← 内置
  query_bank_balance.py
  fill_form_with_id.py

~/.hermes/vault_capabilities/     ← 用户自定义
  query_cmb_balance.py
  query_my_membership.py
```

每个 .py 文件需要：

```python
# ~/.hermes/vault_capabilities/query_cmb_balance.py
from hermes_vault.capability_api import capability, vault_get

@capability(
    name="query_cmb_balance",
    description="查询招商银行余额",
    secret_dependencies=["banking/CMB"],   # 依赖哪些 vault 条目
)
def query_cmb_balance() -> dict:
    card = vault_get("banking/CMB")["card"]   # 临时取，函数返回后释放
    return cmb_api.balance(card)
```

`vault_get()` 在 daemon 进程内访问 KV，不出进程边界。
返回值是 capability 业务值（余额、积分），**不含 vault 字面值**。

daemon 启动 log：

```
[capabilities] loaded 5 built-in
[capabilities] loaded 3 user-defined from ~/.hermes/vault_capabilities/
[capabilities] total 8 tools registered
```

### 5.5 通道 C 远程加密细节

#### 5.5.1 加密协议

X25519（密钥交换）+ XChaCha20-Poly1305（对称加密），用 [tweetnacl-js](https://github.com/dchest/tweetnacl-js)。

服务端 keypair：

```
~/.hermes/vault.unlock.pubkey   (32B, mode 0644, 可公开)
~/.hermes/vault.unlock.privkey  (32B, mode 0600)
```

#### 5.5.2 数据流

```
1. 浏览器 GET https://hermes.<your-domain>/unlock?n=<nonce>
   → vault daemon 返回 HTML + JS bundle + server_pubkey + nonce
2. 浏览器 JS：
   - 显示 server_pubkey fingerprint（用户首次须对比）
   - encrypted = nacl.box(password, nonce, server_pubkey, ephemeral.privkey)
   - POST {ephemeral.pubkey, nonce, ciphertext}
   ↓ 经 tunnel（cloudflare 看到密文）
3. vault daemon：
   - 检查 nonce 未过期未用过
   - plaintext = nacl.box.open(ciphertext, nonce, ephemeral.pubkey, server_privkey)
   - vault.unlock(plaintext)
   - 销毁 ephemeral pubkey 不重用
   - audit log + 推 wechat + telegram 告警
   - 5 秒后关 web server
```

#### 5.5.3 缓解措施清单

| # | 措施 | 防御 |
|---|---|---|
| 1 | 公钥 fingerprint 显示 | 防 tunnel 替换公钥 |
| 2 | SRI lock JS bundle hash | 防 tunnel 改 JS |
| 3 | 严格 CSP + 禁外部资源 | 防注入 |
| 4 | 极简 JS（< 200 行可审计） | 让审计可行 |
| 5 | nonce + 5 分钟 TTL | 防 replay |
| 6 | 失败 3 次 daemon 自杀 | 防 brute force |
| 7 | 成功 5 秒后关 server | 缩攻击窗口 |
| 8 | POST origin 必须匹配 hostname | 防 CSRF / DNS rebinding |
| 9 | rate limit：每 IP 每分钟 1 次 | 防扫描 |
| 10 | audit log + IM 双推告警 | 事后追溯 + 异常立即知晓 |
| 11 | 首次启用通道 C 强制告警 | 防误装暴露 |

#### 5.5.4 残余风险（用户已 explicit opt-in）

```
通道 C 不能防御的：
  - tunnel 提供商主动篡改 JS（host-page-trust 限制）
  - 浏览器恶意扩展读取密码
  - 浏览器密码管理器自动存
  - 用户首次未对比 fingerprint
```

#### 5.5.5 默认开启（v5.1 改用 vault.yaml）

```python
def is_remote_unlock_enabled() -> bool:
    cfg = load_vault_yaml()
    return bool(cfg.get("remote", {}).get("hostname"))
```

`~/.hermes/vault.yaml` 节选：
```yaml
remote:
  hostname: hermes.your-cloudflare.com
  real_ip_header: CF-Connecting-IP
```

设了 hostname → 自动启 + 首次启用强制推 wechat + telegram 告警 "通道 C 已启用，URL: ..."

#### 5.5.6 Tunnel-agnostic

cloudflare → tailscale 等迁移时 hermes_vault 代码 0 改动，只需改 vault.yaml 几行：

| 字段 | cloudflare | tailscale |
|---|---|---|
| `remote.hostname` | `hermes.xxx.cloudflare.com` | `mac-mini.tail-xxxx.ts.net` |
| `remote.real_ip_header` | `CF-Connecting-IP` | `X-Forwarded-For` |
| `remote.allowed_origins` (single) | 上面 hostname | 上面 hostname |

### 5.6 vault.yaml 配置（v5.1 替代原 fallback redactor 章节）

vault daemon 自己的配置文件 `~/.hermes/vault.yaml`（mode 0600）：

```yaml
# ~/.hermes/vault.yaml
remote:
  # 通道 C 远程 unlock 配置（设了就自动启用通道 C）
  hostname: hermes.your-cloudflare.com   # 留空 → 通道 C 禁用
  real_ip_header: CF-Connecting-IP       # 替换 tunnel 时改

# unlock 通道
unlock:
  cool_down_seconds: 30        # daemon 启动后 cool-down（D-13）
  max_failures: 10             # 跨重启失败计数阈值（D-13）
  lockout_hours: 1             # 达阈值后锁定时长

# capability 工具
capabilities:
  user_dir: ~/.hermes/vault_capabilities   # 用户自定义工具目录（D-15）

# 告警
alerts:
  unlock_success:              # unlock 成功推哪些通道
    - wechat
    - telegram
  remote_channel_first_enable: # 通道 C 首次启用推哪些
    - wechat
    - telegram
  daemon_crash:                # daemon 崩溃后重启推哪些（M5）
    - wechat
    - telegram

# 备份
backup:
  rolling_count: 5             # vault.age.bak 保留份数（§5.1.2）
  archive_dir: null            # 可选离线归档目录（推荐手工 cp 到外部介质）
```

**关于脱敏**（v5.1 重定向，删除 v5 的 fallback redactor 方案）：

经审视，v5 的"fallback redactor + 优雅退出"是**过度设计**。理由：
- vault capability 设计纪律是：**不返回 vault 字面值**（公理 I-4）
- capability 内部用 secret 调外部 API，不进 hermes 进程的 stdout / log
- "万一 capability 实现有 bug 打了 secret" 这种情况，redactor 字典也兜不住（capability 取的值跟字典里的形态可能不一致）

→ T6 的真实防御是：
1. **capability 实现规范**：capability 模板给出"不要打 secret 到 log"模式
2. **code review**：每个 capability 文件 PR 时人工 review 一遍
3. **audit log**：调用 + 来源记录在 vault 自己的 audit log

未来 hermes 官方加了 redactor，vault capability 也不需要做什么——hermes 官方 redactor 接管即可。

→ vault 不再装任何 redactor，hermes 主代码继续 0 嵌入，site-packages 不污染。

### 5.7 Claude Code 端硬隔离

`~/.claude/settings.json`（v5.1 收紧 deny 规则，避免误拦合法操作）：

```json
{
  "permissions": {
    "deny": [
      "Read(~/.hermes/vault.age)",
      "Read(~/.hermes/vault.age.bak.*)",
      "Read(~/.hermes/vault.unlock.privkey)",
      "Read(~/.hermes/vault-audit.log)",
      "Bash(cat *vault.age*)",
      "Bash(less *vault.age*)",
      "Bash(head *vault.age*)",
      "Bash(tail *vault.age*)",
      "Bash(strings *vault.age*)",
      "Bash(xxd *vault.age*)",
      "Bash(hexdump *vault.age*)"
    ]
  }
}
```

精准 deny "**读取**" 类命令；不拦"**操作**"类（如 `vault import-from-file vault.age.bak.123` 仍能跑）。

通过 `hermes-vault setup-claude-permissions` 一键写入。

---

## 6. 数据流图

### 6.1 启动 + unlock

```
[launchd] → vault daemon
  ↓
LOCKED 状态，等 unlock，MCP 工具仍可调（返回 vault_locked: true）

[user] $ hermes-vault unlock
  → socket → daemon → SecretVault.unlock(passphrase)
  → status: RUNNING
  → 推 wechat + telegram "vault unlocked"
```

### 6.2 hermes agent 用 vault

```
[user] 跟 hermes bot 说："帮我查招行卡余额"

[hermes agent (LLM)]
  → 看到工具列表中有 vault_list / query_bank_balance
  → 调 vault_list(category="banking") → ["CMB", "ICBC"]
  → 调 query_bank_balance("CMB")
       ↓ MCP → vault daemon
       vault 内部用 CMB 卡号调银行 API
       返回 {balance: 1234.56, currency: "CNY"}
  → 回复用户："您的招行卡余额 1234.56 元"

卡号字面值从未离开 vault daemon。
```

### 6.3 Claude 直接查 vault

```
[user 跟 Claude] "我有几张银行卡？"

[Claude]
  → 调 vault_list(category="banking") → ["CMB", "ICBC"]
  → 回复："您 vault 里有 2 张：招行 / 工行"

[user] "招行卡号是多少？"

[Claude]
  → 知道 vault 不返回字面值
  → 回复："请在终端跑 `hermes-vault show banking/CMB`，密码不进对话"
```

### 6.4 用户直接看 vault

```
[user 在自己终端]
$ hermes-vault show banking/CMB
[OK]: 6225 **** **** 1234

[内容只在用户屏幕，不进任何对话]
```

---

## 7. API

### 7.1 Vault CLI

```
hermes-vault init                    # 创建 vault.age + 强制备份提示
hermes-vault set <NAME>              # prompt 输入值，加密写
hermes-vault show <NAME>             # 终端打印值（用户主动）
hermes-vault list [--category=X]     # 列名字 + kind，不列值
hermes-vault delete <NAME>
hermes-vault rotate-passphrase
hermes-vault import-from-file <path> # 批量导入
hermes-vault unlock [--web] [--remote]
hermes-vault lock
hermes-vault status
hermes-vault reset-failcount         # 解锁阈值锁定（需要主密码确认）
hermes-vault setup-claude-permissions
hermes-vault check-upstream-drift    # hermes upstream sync 时跑（v5.1: 极简）
```

CLI 全部走 unlock socket 跟 daemon 通信（除 `init` 时 daemon 还没起）。

### 7.2 MCP 工具（hermes / Claude 都能调）

见 §5.4.3。

### 7.3 内部 Python API

```python
from hermes_vault import SecretVault

vault = SecretVault.instance()      # 仅 daemon 内部用
secret = vault.get(name)             # 返回 SecretStr
status = vault.status(name)          # 脱敏元数据
```

---

## 8. 部署（不是迁移）

vault 跟 hermes 平行，不替代任何东西，所以不存在"迁移 hermes secret"步骤。

### 8.1 首次安装

```bash
# 1. 安装包
brew install age
pip install hermes-vault              # 独立 Python 包

# 2. 初始化
hermes-vault init                      # prompt 主密码，强制备份确认

# 3. 写 vault.yaml 配置
cat > ~/.hermes/vault.yaml <<EOF
remote:
  hostname: ""    # 留空 → 通道 C 禁用；要远程则填你的 cloudflare 域名
  real_ip_header: CF-Connecting-IP
EOF
chmod 600 ~/.hermes/vault.yaml

# 4. 装 launchd plist
hermes-vault install-launchd

# 5. 配 hermes 集成
cat >> ~/.hermes/config.yaml <<EOF
mcp_servers:
  vault:
    url: "http://127.0.0.1:7860/mcp?client=hermes"
    auth: none
EOF

# 6. 配 Claude Code 集成（按需）
hermes-vault setup-claude-permissions
# Claude Code 端额外手工加一节 mcp_servers.vault url=...?client=claude

# 7. 启动 + 解锁
launchctl load ~/Library/LaunchAgents/ai.hermes.vault.plist
hermes-vault unlock

# 8. 开始往里存
hermes-vault set personal/ID_CARD
hermes-vault set banking/CMB
...
```

### 8.2 卸载

```bash
hermes-vault lock                                         # 清内存
launchctl unload ~/Library/LaunchAgents/ai.hermes.vault.plist
# 编辑 ~/.hermes/config.yaml 删 mcp_servers.vault 节
# vault.age 文件保留（不删，怕用户后悔）
```

---

## 9. 嵌入清单

### 9.1 hermes 主代码改动：**0 行**

（vault 通过 hermes 现有 MCP client 机制自动接入）

### 9.2 hermes 配置改动：1 节

`~/.hermes/config.yaml` 加：

```yaml
mcp_servers:
  vault:
    command: ["python", "-m", "hermes_vault.mcp_server"]
    auth: none
```

**这是用户配置，不是 hermes 仓库内容**——上游升级 0 影响。

### 9.3 全新文件清单

```
独立 Python 包 hermes-vault/:
  hermes_vault/
    __init__.py
    secret_vault.py          ~300  (vault crypto + atomic write + KV)
    daemon.py                ~200  (daemon main loop + 状态机 + cool-down + 失败计数)
    cli.py                   ~250  (init/set/show/list/reset-failcount/...)
    control_socket.py        ~100  (vault-control.sock IPC server)
    mcp_server.py            ~250  (HTTP/SSE MCP, tools list/status/capabilities + caller 区分)
    unlock_web.py            ~250  (B + C 通道 web server)
    capability_api.py        ~80   (@capability 装饰器 + vault_get helper)
    web_assets/
      unlock.html             ~80
      unlock.js              ~150  (X25519 客户端加密)
      tweetnacl.min.js       vendored
    capabilities/             按需扩展，每个 1-2 文件
      query_bank_balance.py
      fill_form.py
      ...

用户目录：
  ~/.hermes/vault_capabilities/                 用户自定义 capability
  ~/.hermes/vault.yaml                          vault 自己的配置

部署文件：
  ~/Library/LaunchAgents/ai.hermes.vault.plist  ~30

文档：
  docs/plans/secret-vault-design.md             (本文档)
```

总：~1600 行新代码，独立 Python 包，跟 hermes 主仓**无 git 关系**（甚至可发独立 PyPI）。
（v5.1 比 v5 少 redactor.py + .pth ~150 行，多 control_socket.py + capability_api.py ~180 行 + daemon.py 扩展 ~50 行 ≈ +80 行净增）

### 9.4 上游升级影响：**0**

hermes 仓库 rebase upstream 完全不涉及 vault。
唯一例外：sync 时跑 `hermes-vault check-upstream-drift` 检查"hermes 是否新增官方 redactor"（→ 触发 fallback 优雅退出）。

---

## 10. 风险

### 10.1 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 主密码忘 = vault 数据全丢 | 强制备份提示（§5.1.4）|
| R2 | vault.age 文件失窃 | age 加密 + 强主密码（§5.1.3）|
| R3 | vault.age 写盘中断锁死 | atomic write + 滚动备份（§5.1.2）|
| R4 | hermes capability 实现 bug 漏 secret 到 log | fallback redactor + capability 实现 review |
| R5 | 通道 C tunnel 主动篡改 JS | 不防（host-page-trust）；fingerprint + SRI + 告警缓解 |
| R6 | 浏览器恶意扩展读密码 | 文档建议 incognito mode |
| R7 | unlock socket 同 UID 冒充 | LOCAL_PEERCRED 校验 + 失败计数 |
| R8 | hermes 没起 → MCP 连不上 | log warning，hermes 照常跑（fail open for vault） |
| R9 | vault 没起 → hermes 看不到 vault 工具 | 同上 |
| R10 | vault daemon 崩溃（OOM / Python exception）| launchd 自动拉起 → 进 LOCKED → IM 推 "vault crashed and re-locked" 告警，用户重新 unlock |
| R11 | capability 实现 bug 把 secret 打到 log | code review + capability 模板规范（无全局 redactor，依靠纪律）|
| R12 | 未来 hermes 加官方 redactor 跟我们冲突 | v5.1 已删 redactor，无冲突可能 |
| R13 | 用户自定义 capability 引入 supply chain 风险 | `~/.hermes/vault_capabilities/` 文件用户自管，文档明示 |

### 10.2 待研究

| # | 问题 | 决议方式 |
|---|---|---|
| U1 | Touch ID 集成 | Phase 4 POC |
| U2 | 跨 Linux 移植 | 暂不考虑，仅 macOS |

---

## 11. 实施阶段

### Phase 0: 环境实测 ✅ 已完成（2026-05-11）

主要发现：
- subprocess.Popen patch 在 v5 不再需要（hermes secret 不动）
- LOCAL_PEERCRED 在 macOS Python 3.13 可用
- launchd KeepAlive 不杀长期 LOCKED daemon
- getpass 在 daemon 不可用，必须 socket

### Phase 0.5: hermes MCP 协议补测 ✅ 已完成（2026-05-11）

实测结论：
- ✅ B1：hermes `tools/mcp_tool.py` **完全支持** `url:` 形式 HTTP/SSE MCP server
- ⚠️ B2：hermes 默认 clientInfo 是 `mcp/0.1.0` 通用值，**不可靠**——caller 区分必须靠 URL `?client=` 约定（D-12 已修订）
- ✅ D2：hermes 容错（3 次初始重试 + 5 次重连，指数 backoff）；隐患：永久放弃后只能靠 config.yaml hot-reload 触发重连 → vault 必须启动早于 hermes (D-23)

依赖：`mcp>=1.2.0,<2` Python SDK，hermes 通过 `[mcp]` extras 安装。

### Phase 1: vault 核心（1 天）

- [ ] `hermes_vault/secret_vault.py`：crypto + atomic write + 强度检查 + 备份提示
- [ ] `hermes_vault/cli.py`：init / set / show / list / delete / import / rotate
- [ ] X25519 keypair 生成 + persist
- [ ] vault.yaml 加载 + schema 校验
- [ ] 单元测试

### Phase 2: daemon + 三通道 unlock（2 天，v5.1 上调 0.5 天）

**Day 2.1**：daemon 框架 + 通道 A
- [ ] `hermes_vault/daemon.py`：daemon main + 状态机（LOCKED/RUNNING）
- [ ] 30s cool-down + 失败计数持久化
- [ ] in-flight capability 调用追踪（lock 走完不中断）
- [ ] 通道 A: vault-control.sock + LOCAL_PEERCRED 校验
- [ ] audit log

**Day 2.2**：通道 B + C
- [ ] 通道 B: web 本地 (127.0.0.1)
- [ ] 通道 C: web 远程 + X25519 + tweetnacl-js + SRI + CSP
- [ ] 首次启用通道 C 强制 wechat + telegram 告警
- [ ] daemon crash 自恢复推 IM 告警

### Phase 3: HTTP/SSE MCP server + capability 扩展（0.5 天）

- [ ] `hermes_vault/mcp_server.py`：HTTP/SSE 实现
- [ ] vault_list / vault_status
- [ ] LOCKED 状态 success+payload 响应
- [ ] caller 区分（MCP init metadata + URL ?client= fallback）
- [ ] capability 扫描 + `~/.hermes/vault_capabilities/*.py` 自动注册
- [ ] 第一个 reference capability（query_bank_balance）
- [ ] hermes config.yaml 加 mcp_servers.vault url 形式

### Phase 4: 部署 + 集成测试（0.5 天）

- [ ] launchd plist
- [ ] hermes-vault setup-claude-permissions
- [ ] hermes-vault check-upstream-drift
- [ ] V1-V24 验收（§12）
- [ ] mac 重启 → vault 自动起 → ssh unlock → hermes 自动连上 MCP → 全流程

**总：4 天**（含 Phase 0.5）。

---

## 12. 验收

| # | 测试 | 期望 |
|---|---|---|
| V1 | `cat ~/.hermes/vault.age` | 输出乱码（age armor），无明文 |
| V2 | Claude 尝试 `Read(~/.hermes/vault.age)` | 被 deny |
| V3 | 不输主密码 → MCP 工具调用 | 返回 `{vault_locked: true, hint: ...}` |
| V4 | 输错主密码 3 次 | daemon 自杀，launchd 重启重置 |
| V5 | 输对主密码 → vault_list 调用 | 返回名字 + kind，不返回值 |
| V6 | vault_get 调用 | 工具不存在 |
| V7 | vault_status("BANK_CMB") | 返回 `{set: true, masked: "****1234"}` |
| V8 | hermes 没起 vault 起 | 用户可 vault show，hermes 不需在线 |
| V9 | vault 没起 hermes 起 | hermes log warning，照常跑，agent 看不到 vault 工具 |
| V10 | 写 vault 中途 SIGKILL | vault.age.bak.<ts> 可恢复 |
| V11 | vault.age 改 0644 | 启动拒启 |
| V12 | vault init 输 "1234" 主密码 | 拒绝，强度不足 |
| V13 | vault init 不输 "yes I backed up both" | 提示未确认备份 |
| V14 | hermes-vault unlock --web 本地浏览器输入 | 解锁成功，密码不进对话 |
| V15 | 故意改 unlock.html 中 JS hash | 浏览器 SRI 拒载 |
| V16 | 未设 HERMES_VAULT_REMOTE_HOSTNAME 跑 --remote | 报错 "remote channel not configured" |
| V17 | 首次设 HOSTNAME 启动 vault | wechat + telegram 收到 "通道 C 已启用" 告警 |
| V18 | 通道 C 远程 unlock 成功 | wechat + telegram 收到 "unlocked from IP X" 告警 |
| V19 | hermes upstream rebase 完跑 check-upstream-drift | 报告 hermes mcp_tool API 是否变化（v5.1: 只看 MCP 兼容性，不再看 redactor）|
| V20 | mac 重启 → launchd 自动起 vault → ssh unlock → hermes 自动看到 vault MCP 工具 | 全流程无手工干预（除 unlock 输密码） |
| V21 | 故意 kill -9 vault daemon | launchd 拉起 → 进 LOCKED → wechat + telegram 收到 "vault crashed and re-locked" 告警（v5.1 R10）|
| V22 | 通道 C 错密码 3 次 → daemon 自杀 → 启动后 30s 内尝试 unlock | 拒绝，返回 "throttled, retry in Ns"（v5.1 D-13）|
| V23 | vault.age 文件被改坏 → `vault restore --from vault.age.bak.<ts>` | 恢复成功，可重新 unlock |
| V24 | 调用 capability 中途 `hermes-vault lock` | 当前 capability 走完，新调用返回 `{vault_locked: true}`（v5.1 H1）|
| V25 | 用户在 `~/.hermes/vault_capabilities/` 加新 .py | daemon 重启后自动扫描注册，MCP 工具列表多一项（v5.1 D-15）|
| V26 | hermes 配 url MCP server，Claude 配 stdio MCP server | 两边均可调，audit log caller 字段区分（v5.1 D-12）|

---

## 13. 决策记录

### v5 全部决策（v1-v4.2 决策已合并/作废）

见 §4.1 D-1 ~ D-10。

---

## 14. 附录

### A. 为什么 vault 不替代 hermes secret

简单的 no-op 原则：**hermes 当前 .env / config.py 体系跑得稳、上游持续迭代，强行替代等于反复跟上游打架**。
vault 定位为"用户私人信息"，跟 hermes 业务凭证天然不同，平行共存最简单。

### B. ~~fallback redactor 检测细节~~（v5.1 删除）

v5 设计的 fallback redactor 经审视为过度设计——见 §5.6。
保留此小节空位以提示历史决策。

### C. capability 设计纪律（v5.1 替代原 .pth 章节）

每个 capability 实现者必须遵守：

1. **不返回 vault 字面值**：返回业务结果（余额、积分），不返回卡号本身
2. **取 secret 用 `vault_get(name)` helper**：函数返回后局部变量被 GC，不在进程内持久驻留
3. **不打 secret 到 log**：`logger.info(f"querying balance for {card}")` ❌ 错误，改 `logger.info("querying balance for ****1234")` ✅
4. **不传 secret 给 subprocess env**：可以，但传完立即 `del`
5. **代码 review**：每个新 capability PR 必须人工 review 确认上述纪律

模板：

```python
# hermes_vault/capabilities/_template.py
from hermes_vault.capability_api import capability, vault_get

@capability(
    name="example",
    description="一句话说明",
    secret_dependencies=["category/KEY"],
)
def example(arg: str) -> dict:
    secret = vault_get("category/KEY")
    # 内部用，不打 log
    result = external_api_call(secret, arg)
    # 不返回 secret 字面值
    return {"result": result.business_value}
```

### D. tunnel-agnostic 设计

详见 §5.5.6。当前 cloudflare，可换 tailscale / nebula / wireguard / 自建反代，hermes_vault 代码 0 改动，只改 vault.yaml 几行。

---

## 15. v5 总览（速查）

| 维度 | 数值 |
|---|---|
| hermes 主代码嵌入 | **0 行** |
| hermes 配置增加 | 1 节（mcp_servers.vault url） |
| 新文件总行数 | ~1600（独立包 hermes-vault） |
| 工作量 | **4 天**（Phase 0 已完成、Phase 0.5 + 1-4） |
| 上游冲突预期 | **0**（vault 跟 hermes 仓无 git 关系） |
| Unlock 通道 | 3 (socket / web 本地 / web 远程经 tunnel) |
| MCP 协议 | **HTTP/SSE**（v5.1，daemon 模式必须）|
| 加密 | age + Argon2id (vault) + X25519 + XChaCha20 (远程通道) |
| Tunnel | cloudflare 当前，tunnel-agnostic 易换 |
| 启动模型 | 独立 launchd plist，跟 hermes 平行 |
| LOCKED 状态 | MCP success+payload `{vault_locked: true, hint: ...}` |
| 脱敏 | **capability 设计纪律**（v5.1 删除 fallback redactor）|
| brute force | daemon 启动 30s cool-down + 失败计数持久化 + 阈值锁定 |

### 实施前 checklist

- [x] Q1-Q4 + D-1 ~ D-15 全部确认（v5.1 加 D-11~D-15）
- [x] Phase 0 实测完成
- [ ] Phase 0.5 hermes MCP 协议补测
- [ ] 准备开 Phase 1：vault crypto + CLI

---

## 16. 上游同步（v5.1 极简版）

**v5/v5.1 跟 hermes 仓 0 git 关系**，sync 流程极简。

唯一相关动作：每次 hermes upstream sync 后跑：

```bash
$ hermes-vault check-upstream-drift
🔍 Checking hermes upstream for vault-relevant changes...

[mcp client]
  ✓ hermes mcp_tool API still supports url-based MCP → vault MCP compatible
  (或) ⚠️  hermes mcp_tool API changed signature → review vault MCP integration

[secret model]
  ✓ hermes still uses .env / config.py for own secrets → vault scope unchanged

[config schema]
  ✓ hermes config.yaml mcp_servers schema unchanged
```

非 0 退出码 → CI / pre-merge hook 阻断。

v5.1 不再检测 hermes 是否新增 redactor（v5 fallback redactor 章节已删）。

---

**END OF DESIGN DOC v5.1**
