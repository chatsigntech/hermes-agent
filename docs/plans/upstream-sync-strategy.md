# 回归 upstream-friendly 的 fork 维护策略

写于 2026-05-04。本文不做修改，只把现状摸清、把每条本地改动分类、定下后续路径，让后面的 upstream 同步代价最小化。

---

## 0. 背景与问题

当前 `nousresearch/hermes-agent` upstream 之间的差距：

- 本 fork 自 4月12日 起，**领先 upstream 18 个本地 commit**
- 同期 upstream 已经向前推进 **~7036 个 commit**（含 5 个 release tag：v2026.4.3 / 4.8 / 4.16 / 4.23 / 4.30）
- 直接 `git merge upstream/main` → 大概率出现核心模块（gateway、agent、hermes_cli）冲突

希望达到的状态：

> **本地 fork 只保留个人 skill / 文档 / 私有配置；所有 fix / feat 走 upstream PR；以后 sync upstream 几乎零冲突。**

---

## 1. 当前 18 个本地 commit 分类

| 分类 | 数量 | 处理方式 |
|---|---:|---|
| **A. 纯 skill / docs / 配置类**（永远不冲突） | 9 | 保留本地，不做处理 |
| **B. 适合直接 upstream PR**（小巧、独立、有测试） | 6 | 各自一个 PR |
| **C. 需要先讨论/拆分的大功能** | 1 | 写设计提案 → upstream issue → 后续拆 PR |
| **D. 已被 revert / 暂停推进** | 2 | 不处理 |
| **E. 维护性自留**（非通用、不上游） | 0 | （暂无） |

合计 18。

### PR 准备度分级标准（用于第 3 节）

- **✅ 高**：commit 有完整 body + 含测试 + 改动 scoped + cherry-pick 到 upstream/main 干净或 ≤1 文件冲突
- **🟡 中**：缺 body / 测试不全 / 2-3 文件冲突
- **🔴 低**：多项缺失 + 4+ 文件冲突，或 upstream 在同区域大改

### Cherry-pick dry-run 实测（在 upstream/main 上分别试 cherry-pick）

| commit | 冲突文件 | 难度 |
|---|---|---|
| B7 `f83a201e` prefer active runtime env | (无) | ✅ 直接 PR |
| B6 `cafcbda0` silence email senders | tests/gateway/test_config.py | ✅ 单文件，易解 |
| B1 `692e4fe2` honor base_url | hermes_cli/auth.py | 🟡 单核心文件 |
| B2 `edadcdb8` redact passwords | agent/redact.py | 🔴 见下文，分歧巨大 |
| B5 `425654b8` memory unresolved | gateway/run.py + run_agent.py + 2 tests | 🟡 4 文件 |
| B3 `e6775c0c` email reply persist | gateway/run.py + 1 test | 🟡 2 文件 |
| B4 `58fb4a09` email replies + attachments | gateway/platforms/base.py + gateway/run.py + 1 test | 🔴 + 大 feature，走 C 类 |

---

## 2. A 类：纯 skill / docs（保留本地）

完全不动核心代码，merge upstream 时永远干净。继续保留：

| commit | 含义 |
|---|---|
| `bc4f90d feat(skills): add cloudflared ssh setup workflow` | skills/devops/cloudflared-ssh-setup/SKILL.md |
| `b31bfdb chore(gitignore): ignore .DS_Store` | 单行 .gitignore（macOS 用户通用，可 PR 也可不 PR） |
| `b1acda8 docs(control-tower): tighten bootstrap safeguards` | website/docs |
| `67f49151 feat(skills): add ssh key onboarding workflow` | skills/devops/ssh-key-onboarding/SKILL.md |
| `f91d263c docs(security): add Hermes Vault architecture guide` | website/docs |
| `eb94b437 docs(control-tower): track worker sessions explicitly` | website/docs |
| `51d7b90a docs(control-tower): refine remote and single-worker workflow` | website/docs |
| `0afadd7 feat(skills): add moss-tts voice cloning skill` | skills/mlops/models/moss-tts/SKILL.md（这次 session 加的） |
| `7de9e204 feat(control-tower): add software development orchestration skill` | 1939 行新增，全是 skill + 模板 + guide |

**`b31bfdb chore(gitignore): ignore .DS_Store`** 单独说明：是单行 `.DS_Store` 加进 .gitignore，upstream 可能愿意收，也可以顺手提个 micro-PR，零风险。

---

## 3. B 类：适合直接走 PR（6 条，按推荐执行顺序）

按 cherry-pick dry-run 实测难度 + 价值排序。**先做最干净的，建立 PR 节奏**，再啃硬骨头。

### B7 — `f83a201e fix(gateway): prefer active runtime env for services` 【先做】

- **改动范围**：`hermes_cli/gateway.py` (+45/-) + 测试
- **做了什么**：service 启动时优先使用当前活跃的 runtime env（无 body）
- **dry-run 结果**：✅ **干净 cherry-pick，0 冲突**
- **PR 准备度**：✅ **高**（cherry-pick clean + 有测试，只缺 body 说明）
- **建议动作**：补 commit body 后立即 PR
- **建议 PR 标题**：`fix(gateway): prefer active runtime env when launching services`

### B6 — `cafcbda0 fix(email): silence unauthorized senders` 【先做】

- **改动范围**：`gateway/config.py` + `gateway/run.py` + `hermes_cli/config.py` + 测试 + 文档（共 9 文件）
- **做了什么**：未授权 email 发件人不再触发可见回复（无 body，但有充分文档+测试）
- **dry-run 结果**：⚠️ 单文件冲突 `tests/gateway/test_config.py`（test 改动易解）
- **PR 准备度**：✅ **高**（功能/文档完整，仅 1 个测试文件冲突，且不是核心代码）
- **建议动作**：rebase 到 upstream/main，手解 test_config.py 冲突，补 body，PR

### B1 — `692e4fe2 fix(auth): honor config.yaml base_url for API-key providers`

- **改动范围**：`hermes_cli/auth.py` (+33/-2) + 配套测试 30 行
- **做了什么**：Kimi / Zai 等 API-key 提供商现在会读 `config.yaml` 里的 `model.base_url`；按 provider_id scope；环境变量优先级保留
- **dry-run 结果**：⚠️ 单文件冲突 `hermes_cli/auth.py`
- **upstream 相邻活动**（要看是否已被覆盖）：
  - `6cf7a9e3 fix(vision): preserve explicit provider auth with custom base_url`
  - `3c420245 fix(curator): pass auxiliary curator api_key/base_url into runtime resolution`
  - `0ddc8aba fix(fallback): let custom_providers shadow built-in aliases`
- **PR 准备度**：🟡 **中**（commit body 完整、有测试，但 hermes_cli/auth.py 跟 upstream 有交叠）
- **建议动作**：rebase 后**先读 upstream/main 上 auth.py 的当前实现**，确认我们这条 fix 还有意义（可能已被覆盖）；如果还有意义，手解冲突然后 PR

### B3 — `e6775c0c fix(gateway): persist pending email reply approvals`

- **改动范围**：`gateway/run.py` (+31/-3) + 测试 55 行
- **做了什么**：让 email 回复审批（pending）持久化（无 body）
- **dry-run 结果**：⚠️ 2 文件冲突 `gateway/run.py` + `tests/gateway/test_email_reply_approval.py`
- **PR 准备度**：🟡 **中**（缺 body + gateway/run.py 是 hot file）
- **依赖关系**：跟 B4 同系列功能，技术上**应合并 PR 或先 PR**
- **建议动作**：和 B4 共同决策（见 C 类）；如果 B4 走 issue 路线，B3 可以独立 PR

### B5 — `425654b8 fix(memory): block unresolved troubleshooting notes`

- **改动范围**：`tools/memory_tool.py` (+28/-2) + `gateway/run.py` 微调 + `run_agent.py` 微调 + 多处测试
- **做了什么**：阻止"未解决"标记的 troubleshooting note 被持久化（无 body）
- **dry-run 结果**：⚠️ 4 文件冲突 `gateway/run.py` + `run_agent.py` + 2 测试
- **PR 准备度**：🟡 **中**（缺 body + 4 文件冲突，但每处改动小）
- **建议动作**：补 body 后做 cherry-pick，预计 30 分钟内手解完所有冲突
- **建议 PR 标题**：`fix(memory): block unresolved troubleshooting notes from persistence`

### B2 — `edadcdb8 fix(logging): redact password-like values in logs` 【最难，可能放弃】

- **改动范围**：`agent/redact.py` (+45/-7) + 测试 31 行
- **做了什么**：扩展密码风格的字符串脱敏（无 commit body）
- **dry-run 结果**：🔴 冲突 `agent/redact.py`
- **实测分歧大小**：
  - 本地改了 **47 行**
  - upstream 同区域改了 **257 行**（5.5 倍），跨 6 个 commit
  - 主要 upstream 活动：`6f864f8f code_file param`、`8c892c14 canonical mask_secret helper`、`8081425a make secret redaction off by default`、`ee9c0a3e JWT/Discord token redaction`
- **PR 准备度**：🔴 **低**。upstream redact 模块已经被大改，我们这条 47 行 patch 大概率已经被涵盖在 upstream 的某条 commit 里，或者用了不兼容的新 helper（`mask_secret`）
- **建议动作**：**先读 upstream 当前 `agent/redact.py`**，对比我们要的"密码风格脱敏"是否已经被 upstream 实现：
  - 是 → **丢弃我们这条 commit**（不 PR），merge upstream 后行为已等价
  - 否 → 在 upstream 新 helper（`mask_secret`）基础上重写一个 patch 再 PR，**不要硬移植**

---

## 4. C 类：需要先讨论的大功能（1 条）

**`58fb4a09 feat(gateway): add approved email replies and file attachments`**

- **改动范围**：8 文件 +509/-15，其中 `gateway/run.py` 新增 226 行
- **dry-run 结果**：🔴 3 文件冲突 `gateway/platforms/base.py` + `gateway/run.py` + `tests/gateway/test_platform_base.py`
- **是功能扩展不是 fix**：upstream 收不收是产品决策，不只是技术决策

**建议路径**：
1. 在 upstream 仓库开 GitHub Issue：「Proposal: approved email replies + file attachments」
2. 描述用户需求 + 简短设计 + 截图/示例（可以引用 B3 作为相关 fix）
3. 等 maintainer 反馈：要不要、要的话怎么拆
4. 反馈后再决定 PR 拆分粒度（initial 想法）：
   1. config 字段（小，独立）
   2. base.py 平台基类扩展（中）
   3. run.py 主流程接入（大）
   4. CLI 命令（小，独立）

---

## 5. D 类：已 revert / 暂停（2 条）

| commit | 状态 |
|---|---|
| `2edcff5 feat(telegram): channel-post intake and DoH IP-fallback transport` | 已 revert |
| `70c0517 Revert "feat(telegram): channel-post intake..."` | revert commit 本身 |

不处理。如果以后想做 telegram channel post 功能，重新设计、且参考 upstream 当前 telegram_network.py 的最新版本。

---

## 6. E 类：维护性自留（暂无）

目前没有需要"明确不上游、自己维护"的 commit。如果将来出现（比如某个 fix 跟你独有部署绑定），写到这里并加注解释。

---

## 7. Workflow 流程（PR 操作手册）

### 7.1 一次性准备

```bash
# 1. GitHub 上 fork nousresearch/hermes-agent 到自己账号
#    （操作在 web 端：https://github.com/nousresearch/hermes-agent → Fork）

# 2. 给本地 repo 加 origin remote（指你自己的 fork）
git remote add origin git@github.com:<your-handle>/hermes-agent.git
git remote -v   # 验证

# 3. 默认上游设为 nousresearch（已存在，但 push URL 是 DISABLED）
#    保持只读 fetch，不覆盖
```

### 7.2 每个 PR 的标准流程

以 B1 (`692e4fe2`) 为例：

```bash
# 1. 从最新的 upstream/main 拉一个干净分支
git fetch upstream
git checkout -b fix-auth-base-url upstream/main

# 2. cherry-pick 你的 commit
git cherry-pick 692e4fe2
#    若有冲突：手解 → git add → git cherry-pick --continue
#    没有 body 的 commit 在这一步用 git commit --amend 补完整 message

# 3. 如有需要，跑测试确认还能通过
venv/bin/python -m pytest tests/hermes_cli/test_api_key_providers.py -v

# 4. push 到自己的 fork
git push -u origin fix-auth-base-url

# 5. GitHub 上发 PR
#    base: nousresearch/hermes-agent main
#    compare: <your-handle>/hermes-agent fix-auth-base-url
```

### 7.3 PR merge 后的本地清理

upstream merge 你的 PR 后：

```bash
git checkout main
git fetch upstream
git rebase upstream/main
#    如果你的 commit 跟 upstream 上 merge 的版本完全等价，rebase 自动跳过
#    如果略有差异，可能要 git rebase --skip 或手解一下
```

### 7.4 长期维护：每次 sync upstream

```bash
git fetch upstream
git rebase upstream/main
#    A 类（skill/docs）会干净地堆在 upstream 之上
#    B-C-D 类如果都已 PR / revert 清理过，就没东西在这里冲突
```

---

## 8. 行动计划（按优先级）

### 阶段 1（现在 → 本周内）— 立 PR 节奏

按实测难度递增推进：

1. **GitHub fork** `nousresearch/hermes-agent` + 加 `origin` remote
2. **B7 干净 PR**（cherry-pick clean，30 分钟搞定）— 用这个建立 PR 模板
3. **B6 单测试文件 PR**（30-60 分钟）
4. **B1 单核心文件 PR**（先 read upstream auth.py，1-2h）

完成 1-4 后，你已经有了第一组 review 反馈，知道 maintainer 节奏。

### 阶段 2（一周内）— 处理中等冲突

5. **B5 多文件 PR**（4 文件冲突，每处小，30-60 分钟）
6. **B3 PR**（与 B4 协调，2 文件冲突）
7. **B2 决策**：读 upstream 当前 `agent/redact.py` →
   - 已覆盖 → **丢弃 commit，不 PR**（直接退役）
   - 未覆盖 → 基于 upstream 新 API 重写后 PR

### 阶段 3（一周内）— 大功能进 issue 流程

8. **B4 在 upstream 开 Issue**，附设计提案
9. 等 maintainer 反馈，期间不动 B4 commit

### 阶段 4（PR merge 后）— 本地清理

10. 每个 PR merge 后 `git fetch upstream && git rebase upstream/main`
11. 等价 commit 自动跳过；不等价的会停下让你 `--skip` 或手解
12. 最终本地分支只剩 A 类（skill/docs）+ 还未 merge 的 PR commits
13. 验证 hermes 在 upstream 最新代码 + 你本地 skill 上能正常跑

### 阶段 5（习惯固化）

14. 以后**任何核心改动**：先 fork 上开分支 → push → PR → 等 merge → sync。本地 main 永远只 trail 在 upstream 上的小幅 skill/doc 增量
15. 维护一份 `docs/plans/upstream-sync-tracker.md` 记录每个 PR 的状态

---

## 9. 决策建议与执行结果

- [x] **B1, B5, B6, B7 准备 PR**（4 条 fix）：本地分支已就绪，cherry-pick + 解冲突 + 完整 body。等明确授权后 push + create PR
- [x] **B3 中止**：实测发现它依赖 B4 引入的 `_pending_email_replies` 字段，upstream 完全没有，独立 PR 会引入悬空字段。等 B4 issue 流程结果一并处理
- [x] **B2 (redact) 暂缓**：调研后发现 upstream 已覆盖 query string + JSON body + 已知 prefix，但**不覆盖**自然语言 `password: hunter2` / `密码：xxx` / `password = input()` 模式，还有真实价值。但需基于 upstream 新 API 重写，不是简单 cherry-pick。先做前 4 个 PR 拿反馈节奏，再决定是否值得投入重写
- [x] **B4 (email replies + attachments) 走 Issue 路径**：草稿已写到 `docs/plans/upstream-issue-b4-email-replies.md`，待人工去 GitHub web 提交 issue
- [x] **fork 仓库名用默认 `hermes-agent`**：fork 已建在 `chatsigntech/hermes-agent`
- [ ] **建跟踪表 `docs/plans/upstream-sync-tracker.md`**：等真有 PR 提交后再起

## 9.1 当前实际状态（2026-05-05）

| 状态 | 项目 | 备注 |
|---|---|---|
| ✅ 完成 | 策略文档 commit 到 main | 2 个 commit |
| ✅ 完成 | fork + B7 push 到 origin | 5月4日已 push 到 `chatsigntech/hermes-agent` 的 `fix-gateway-prefer-active-runtime-env` 分支 |
| ✅ 完成 | B7 PR-ready 分支 `fix-gateway-prefer-active-runtime-env` | commit `f25f696a`，无冲突，cherry-pick clean |
| ✅ 完成 | B6 PR-ready 分支 `fix-email-silence-unauthorized-senders` | commit `f9199177`，1 测试文件冲突已解，重写更详细 body |
| ✅ 完成 | B1 PR-ready 分支 `fix-auth-honor-config-base-url` | commit `59e6579b`，1 文件冲突已解（适配 upstream 把 kimi-coding 扩展到 `("kimi-coding", "kimi-coding-cn")` tuple） |
| ✅ 完成 | B5 PR-ready 分支 `fix-memory-block-unresolved-notes` | commit `e71905dc`，scope 缩到只剩 `tools/memory_tool.py`（gateway/run.py + run_agent.py 的 prompt 改动被 upstream 重构作废，2 个测试文件被 upstream 删掉） |
| ✅ 完成 | B4 issue 草稿 | `docs/plans/upstream-issue-b4-email-replies.md` |
| ❌ 中止 | B3 cherry-pick | 依赖 B4 字段，分支已删 |
| ⏸ 延后 | B2 重写 | 决策依据：先看前 4 个 PR 反馈 |
| ⏸ 等待授权 | 4 个 PR `git push origin <branch>` + `gh pr create` | 上次 B7 push 之后用户表达了希望谨慎，需明确授权后再 batch 推 |
| ⏸ 等待人工 | B4 issue 提交 | 需要去 GitHub web 提交 |

下一步用户决策：
1. 授权 push + create 4 个 PR（一次性 batch）
2. 还是先 push 不 create PR，让你 review fork 上的分支
3. 还是再等等，先 review 当前所有本地 commits

---

## 10. 不做这件事的代价

如果维持现状不动：

- **每过 1 周** upstream 多积累几十个 commit，merge 难度递增
- 每次想跟 upstream 同步**都得花半天**手解冲突
- upstream 修过的 bug 你本地版本可能仍然有（因为代码不一样）
- 反过来，你修过的 bug 可能某天 upstream 用不同方式修了，导致 merge 时手撞
- **fork 慢慢变成事实上的"另一个项目"**，失去 upstream 改进红利

按上面阶段 1-4 推进，1 个月内可以回到"几乎零摩擦同步"的状态。
